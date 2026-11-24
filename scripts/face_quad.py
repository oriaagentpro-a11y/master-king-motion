"""Les 4 coins de la FACE d'une carte unie (notification blanche, carte de couleur) image par image, par droites
ajustées sur ses bords (règle 133). Pour les cartes qui bougent vite et que l'alignement de texture (ECC) perd.

Usage: python3 face_quad.py ref.mp4 f0 f1 out.json --hex FFFFFF --tol 10 [--roi x,y,w,h] [--near x,y] [--id carte]
                            [--min-area 3000] [--open 15] [--debug dir]
- pixels à moins de --tol (distance max par canal) de --hex ; pour un blanc pur, --tol 8-12 écarte la dalle translucide
  et les reflets (blancs rosés / bleutés) qui faussaient le quadrilatère (cas Monniz : ombre prise dans le masque) ;
- composante gardée : la plus grande dans la ROI qui NE TOUCHE PAS le bord de l'image (le fond blanc hors téléphone
  la touche), ou la plus proche de --near (x,y suivi d'une image à l'autre) ;
- coins : enveloppe -> 4 sommets (approxPolyDP), puis pour chaque côté une droite ajustée (cv2.fitLine) sur les points
  du contour situés entre les deux sommets, en écartant 18 % aux deux bouts (coins arrondis) ; coins = intersections.
Sortie (format homography_track, lisible par card_pose.py) : {"corners": {f: [[x,y]x4] TL TR BR BL}, "area": {f: n}}
"""
import os as _o, sys as _s; _s.path.insert(0, _o.path.dirname(_o.path.abspath(__file__))); import _mkpy  # noqa: E401,E702,F401
import sys, os, json
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mkcommon as mk  # noqa: E402


def order(q):
    q = np.array(q, float); s = q.sum(1); d = q[:, 0] - q[:, 1]
    return np.array([q[np.argmin(s)], q[np.argmax(d)], q[np.argmax(s)], q[np.argmin(d)]])


def side_line(cnt, a, b):
    """points du contour entre les sommets a et b (sans les 18 % des bouts) -> droite (point, direction)"""
    ab = b - a; L = np.linalg.norm(ab); u = ab / L; n = np.array([-u[1], u[0]])
    t = (cnt - a) @ u; dist = np.abs((cnt - a) @ n)
    sel = (t > 0.18 * L) & (t < 0.82 * L) & (dist < max(6, 0.08 * L))
    pts = cnt[sel]
    if len(pts) < 8:
        return a, u
    vx, vy, x0, y0 = cv2.fitLine(pts.astype(np.float32), cv2.DIST_HUBER, 0, 0.01, 0.01).ravel()
    return np.array([x0, y0]), np.array([vx, vy])


def inter(p1, d1, p2, d2):
    A = np.array([d1, -d2]).T
    if abs(np.linalg.det(A)) < 1e-9:
        return p1
    t = np.linalg.solve(A, p2 - p1); return p1 + t[0] * d1


def main():
    a = sys.argv
    if len(a) < 5:
        sys.exit(__doc__)
    video, f0, f1, out = a[1], int(a[2]), int(a[3]), a[4]
    hx = mk.arg(a, 'hex', 'FFFFFF'); col = np.array([int(hx[i:i + 2], 16) for i in (4, 2, 0)])   # BGR
    tol = mk.arg(a, 'tol', 10, int); roi = mk.arg(a, 'roi'); near = mk.arg(a, 'near'); mina = mk.arg(a, 'min-area', 3000, int)
    dbg = mk.arg(a, 'debug')
    if dbg:
        os.makedirs(dbg, exist_ok=True)
    cap = cv2.VideoCapture(video); cap.set(cv2.CAP_PROP_POS_FRAMES, f0)
    res, area = {}, {}
    last = np.array(list(map(float, near.split(',')))) if near else None
    for f in range(f0, f1 + 1):
        ok, im = cap.read()
        if not ok:
            break
        H, W = im.shape[:2]
        m = (np.abs(im.astype(int) - col).max(2) <= tol).astype(np.uint8)
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))   # trous du texte
        k_open = mk.arg(a, 'open', 15, int)   # séparation : érosion forte (coupe le liseré d'une dalle qui relie la face au fond)
        m_full = m.copy(); m = cv2.erode(m, np.ones((k_open, k_open), np.uint8))
        bx0, by0, bx1, by1 = 0, 0, W, H   # bords qui disqualifient une composante (image, ou ROI si donnée)
        if roi:
            x, y, w, h = map(int, roi.split(',')); keep = np.zeros_like(m); keep[y:y + h, x:x + w] = 1; m &= keep
            bx0, by0, bx1, by1 = x, y, x + w, y + h
        n, lab, st, cen = cv2.connectedComponentsWithStats(m, 8)
        cands = []
        for i in range(1, n):
            x, y, w, h, ar = st[i]
            if ar < mina or x <= bx0 or y <= by0 or x + w >= bx1 or y + h >= by1:
                continue
            cands.append((i, ar, cen[i]))
        if not cands:
            continue
        i = min(cands, key=lambda c: np.linalg.norm(c[2] - last))[0] if last is not None else max(cands, key=lambda c: c[1])[0]
        comp = (lab == i).astype(np.uint8)
        comp = cv2.dilate(comp, np.ones((k_open + 2, k_open + 2), np.uint8)) & m_full   # reconstruction dans le masque d'origine
        comp = cv2.morphologyEx(comp, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
        cs, _ = cv2.findContours(comp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        c = max(cs, key=cv2.contourArea); hull = cv2.convexHull(c)
        q = None
        for eps in np.linspace(0.01, 0.1, 30):
            ap = cv2.approxPolyDP(hull, eps * cv2.arcLength(hull, True), True)
            if len(ap) == 4:
                q = order(ap.reshape(4, 2)); break
        if q is None:
            q = order(cv2.boxPoints(cv2.minAreaRect(c)))
        cnt = c.reshape(-1, 2).astype(float)
        L = [side_line(cnt, q[k], q[(k + 1) % 4]) for k in range(4)]
        corners = [inter(*L[(k - 1) % 4], *L[k]) for k in range(4)]   # sommet k = côté (k-1) ∩ côté k
        res[f] = [[round(float(p[0]), 2), round(float(p[1]), 2)] for p in corners]; area[f] = int(st[i, 4])
        last = np.array(corners).mean(0)
        if dbg:
            o = im.copy(); cv2.polylines(o, [np.array(corners, np.int32)], True, (255, 0, 255), 2)
            cv2.imwrite(os.path.join(dbg, f'f{f:05d}.png'), o)
    mk.save_json({'corners': res, 'area': area, 'source': video, 'hex': hx, 'tol': tol}, out)
    print(f'{len(res)}/{f1 - f0 + 1} images -> {out}')


if __name__ == '__main__':
    main()
