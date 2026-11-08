"""Recrée une image (vue d'interface, écran, illustration plate) en SVG vectoriel par calques de couleurs (règle 93).

Usage: python3 vectorize_image.py ref.mp4 frame out.svg   |   vectorize_image.py --image planche.png out.svg [--size W,H] [--quad x,y,x,y,x,y,x,y] [--size W,H] [--k 18] [--up 3] [--eps 0.4]
- --quad : zone de l'image redressée en rectangle (coins sens horaire depuis le haut-gauche) ; sinon l'image entière.
- les couleurs sont regroupées en k teintes (k-moyennes, en Lab), chaque teinte devient un calque de chemins (contours
  sur-échantillonnés --up fois, simplifiés de --eps pixels), empilés du plus clair au plus sombre en partant d'un fond plein.
--layered [--kb 22 --kd 26 --sigma 6 --thr 9] : fond lisse + calque de détails (recommandé pour les interfaces).
Sortie : un SVG autonome (viewBox = taille du canevas) que le film pose sur les coins mesurés par homography_track.py.
C'est une RECONSTRUCTION vectorielle (couleurs et formes modifiables, aucune image bitmap copiée) ; pour l'adaptation, le
contenu de l'utilisateur remplace ce SVG sur les mêmes coins.
"""
import sys
import numpy as np
import cv2

sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import mkcommon as mk  # noqa: E402


def paths_for(lbl, ids, cols, W, H, up, eps, minA=1.5, smooth=0.45):
    out = []
    for ci in ids:
        m = (lbl == ci).astype(np.uint8)
        if not m.any():
            continue
        mu = cv2.resize(m.astype(np.float32), (W * up, H * up), interpolation=cv2.INTER_LINEAR if smooth == 0 else cv2.INTER_NEAREST)
        if smooth > 0:
            mu = cv2.GaussianBlur(mu, (0, 0), up * smooth)
        mu = mu > (0.5 if smooth > 0 else 0.35)
        cs, _ = cv2.findContours(mu.astype(np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
        parts = []
        for c in cs:
            if cv2.contourArea(c) < up * up * minA:
                continue
            ap = cv2.approxPolyDP(c, eps * up, True).reshape(-1, 2) / up
            if len(ap) >= 3:
                parts.append('M' + 'L'.join(f'{x:.1f} {y:.1f}' for x, y in ap) + 'Z')
        if parts:
            c_ = cols[ci]; out.append(f'<path fill="#{c_[2]:02x}{c_[1]:02x}{c_[0]:02x}" fill-rule="evenodd" d="{"".join(parts)}"/>')
    return out


DET_MINA, DET_SMOOTH = 0.6, 0.45


def layered(im, out, kb, kd, up, eps, sigma, thr):
    """--layered : FOND lisse (image très floutée, posterisée en kb teintes, puis re-floutée par un filtre SVG = dégradé
    continu) + DÉTAILS (pixels qui s'écartent du fond de plus de --thr en luminance : textes, bougies, icônes, filets),
    quantifiés en kd teintes prises sur ces seuls pixels -> les petits éléments clairs/sombres gardent leur vraie couleur
    au lieu d'être noyés dans le dégradé (défaut du mode simple, plafond ~0,88 sur les interfaces)."""
    H, W = im.shape[:2]
    base = cv2.GaussianBlur(im, (0, 0), sigma)
    lab_b = cv2.cvtColor(base, cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(np.float32)
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.5)
    _, lb, cb = cv2.kmeans(lab_b, kb, None, crit, 2, cv2.KMEANS_PP_CENTERS)
    lb = lb.reshape(H, W); colb = cv2.cvtColor(cb.reshape(1, -1, 3).astype(np.uint8), cv2.COLOR_LAB2BGR).reshape(-1, 3)
    ordb = np.argsort(-np.bincount(lb.ravel(), minlength=kb)); bg = colb[ordb[0]]
    L = cv2.cvtColor(im, cv2.COLOR_BGR2LAB).astype(np.float32); Lb = cv2.cvtColor(base, cv2.COLOR_BGR2LAB).astype(np.float32)
    dev = np.abs(L - Lb); det = (dev[..., 0] > thr) | (np.hypot(dev[..., 1], dev[..., 2]) > thr * 1.2)
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" shape-rendering="geometricPrecision">',
           f'<defs><filter id="sm" x="-5%" y="-5%" width="110%" height="110%"><feGaussianBlur stdDeviation="{sigma * 0.9:.1f}"/></filter></defs>',
           f'<rect width="{W}" height="{H}" fill="#{bg[2]:02x}{bg[1]:02x}{bg[0]:02x}"/>', '<g filter="url(#sm)">']
    svg += paths_for(lb, ordb[1:], colb, W, H, 1, 1.0, 4)
    svg.append('</g>')
    if det.sum() > kd * 4:
        pix = L[det].reshape(-1, 3)
        _, ld, cd = cv2.kmeans(pix, kd, None, crit, 2, cv2.KMEANS_PP_CENTERS)
        lab_d = np.full((H, W), -1, np.int32); lab_d[det] = ld.ravel()
        cold = cv2.cvtColor(cd.reshape(1, -1, 3).astype(np.uint8), cv2.COLOR_LAB2BGR).reshape(-1, 3)
        ordd = np.argsort(cd[:, 0])        # du plus sombre au plus clair : le clair (texte) passe dessus
        svg += paths_for(lab_d, ordd, cold, W, H, up, eps, DET_MINA, DET_SMOOTH)
    svg.append('</svg>')
    open(out, 'w').write('\n'.join(svg))
    print(f'{W}x{H}, fond {kb} + détails {kd} teintes ({det.mean():.1%} px) -> {out} ({sum(len(x) for x in svg) // 1024} Ko)')


def main():
    a = sys.argv
    if len(a) < 4:
        sys.exit(__doc__)
    if a[1] == '--image':      # planche redressée (rectify_median.py) : déjà sur le canevas
        im = cv2.imread(a[2]); out = a[3]
        if mk.arg(a, 'size'):
            im = cv2.resize(im, tuple(map(int, mk.arg(a, 'size').split(','))), interpolation=cv2.INTER_AREA)
    else:
        src, f, out = a[1], int(a[2]), a[3]
        cap = cv2.VideoCapture(src); cap.set(cv2.CAP_PROP_POS_FRAMES, f); ok, im = cap.read()
    if a[1] != '--image' and mk.arg(a, 'quad'):
        q = np.array([float(v) for v in mk.arg(a, 'quad').split(',')], np.float32).reshape(4, 2)
        W = int(round(np.linalg.norm(q[1] - q[0]))); H = int(round(np.linalg.norm(q[3] - q[0])))
        if mk.arg(a, 'size'):
            W, H = map(int, mk.arg(a, 'size').split(','))
        M = cv2.getPerspectiveTransform(q, np.float32([[0, 0], [W, 0], [W, H], [0, H]])); im = cv2.warpPerspective(im, M, (W, H), flags=cv2.INTER_CUBIC)
    H, W = im.shape[:2]; k = mk.arg(a, 'k', 18, int); up = mk.arg(a, 'up', 3, int); eps = mk.arg(a, 'eps', 0.4, float)
    if mk.arg(a, 'layered'):
        global DET_MINA, DET_SMOOTH
        DET_MINA = mk.arg(a, 'mina', 0.6, float); DET_SMOOTH = mk.arg(a, 'smooth', 0.45, float)
        return layered(im, out, mk.arg(a, 'kb', 22, int), mk.arg(a, 'kd', 26, int), up, eps, mk.arg(a, 'sigma', 6.0, float), mk.arg(a, 'thr', 9.0, float))
    lab = cv2.cvtColor(im, cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(np.float32)
    _, lbl, cen = cv2.kmeans(lab, k, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.5), 3, cv2.KMEANS_PP_CENTERS)
    lbl = lbl.reshape(H, W)
    cols = cv2.cvtColor(cen.reshape(1, -1, 3).astype(np.uint8), cv2.COLOR_LAB2BGR).reshape(-1, 3)
    order = np.argsort(-np.bincount(lbl.ravel(), minlength=k))   # la teinte la plus étendue = fond
    bgc = cols[order[0]]
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" shape-rendering="geometricPrecision">',
           f'<rect width="{W}" height="{H}" fill="#{bgc[2]:02x}{bgc[1]:02x}{bgc[0]:02x}"/>']
    for ci in order[1:]:
        m = (lbl == ci).astype(np.uint8)
        mu = cv2.resize(m, (W * up, H * up), interpolation=cv2.INTER_NEAREST)
        mu = cv2.GaussianBlur(mu.astype(np.float32), (0, 0), up * 0.45) > 0.5
        cs, _ = cv2.findContours(mu.astype(np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
        parts = []
        for c in cs:
            if cv2.contourArea(c) < up * up * 1.5:
                continue
            ap = cv2.approxPolyDP(c, eps * up, True).reshape(-1, 2) / up
            if len(ap) >= 3:
                parts.append('M' + 'L'.join(f'{x:.1f} {y:.1f}' for x, y in ap) + 'Z')
        if parts:
            c_ = cols[ci]; svg.append(f'<path fill="#{c_[2]:02x}{c_[1]:02x}{c_[0]:02x}" fill-rule="evenodd" d="{"".join(parts)}"/>')
    svg.append('</svg>')
    open(out, 'w').write('\n'.join(svg))
    print(f'{W}x{H}, {k} teintes -> {out} ({sum(len(s) for s in svg) // 1024} Ko)')


if __name__ == '__main__':
    main()
