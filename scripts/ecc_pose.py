"""Suivi PLANAIRE EXACT d'éléments d'UI (cartes, pilules, bulles, icônes) par ECC sur les pixels de la référence (règle 139).
Remplace la reconstruction « quad depuis le contour » qui déforme les éléments dès qu'ils sont flous, en fondu ou collés
à un autre objet. Ici : un gabarit (le vrai rendu de l'élément à une image nette, l'« ancre ») est recalé image par image
par homographie (cv2.findTransformECC, pyramide 1/4-1/2-1, prédiction à vitesse constante), en avant et en arrière de
l'ancre. Le rectangle de l'élément à l'ancre est projeté par l'homographie : c'est un vrai rectangle en perspective
(jamais un trapèze inventé), à sa taille réelle. Le gabarit se rafraîchit quand l'apparence change (texte qui s'écrit,
remplissage), sans changer sa géométrie.
Mesures par image : quad (4 coins, px réf.), cc (corrélation ECC, fiabilité), alpha (opacité : encre moyenne de
l'élément / encre à l'ancre, robuste au flou car le flou conserve l'encre).

Usage: python ecc_pose.py ref.mp4 spec.json out.json [--check dir]
spec = {"pad": 300, "elements": [{"id": "pill", "f0": 0, "f1": 41, "anchor": 12,
          "seed": [x, y], "thr": 10      # rectangle de l'ancre = composante autour de seed (|I-fond| > thr), minAreaRect
          | "quad": [[x,y]x4]            # ou rectangle donné (TL, TR, BR, BL)
          "margin": 16, "min_cc": 0.55}]}
Sorties : {"elements": {id: {"anchor_quad": [...], "frames": {f: {"quad", "cc", "alpha"} | null}}}}
--check dir : une image par élément (ancre + quelques images avec le quad suivi) à REGARDER avant de s'en servir.
"""
import os as _o, sys as _s; _s.path.insert(0, _o.path.dirname(_o.path.abspath(__file__))); import _mkpy  # noqa: E401,E702,F401
import sys, json, os
import numpy as np
import cv2


def order(pts):
    pts = np.array(pts, float); c = pts.mean(0); a = np.arctan2(pts[:, 1] - c[1], pts[:, 0] - c[0])
    p = pts[np.argsort(a)]                       # sens horaire écran à partir de -pi
    i = np.argmin(p.sum(1)); return np.roll(p, -i, 0)   # TL, TR, BR, BL


def anchor_quad(g, seed, thr, close=5):
    m = (np.abs(g.astype(np.int16) - 255) > thr).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((close, close), np.uint8))
    n, lab = cv2.connectedComponents(m); l = lab[seed[1], seed[0]]
    if l == 0:
        ys, xs = np.nonzero(lab); d = (xs - seed[0]) ** 2 + (ys - seed[1]) ** 2; l = lab[ys[d.argmin()], xs[d.argmin()]]
    ys, xs = np.nonzero(lab == l); r = cv2.minAreaRect(np.stack([xs, ys], 1).astype(np.float32))
    return order(cv2.boxPoints(r))


def proj(H, Q):
    q = np.c_[Q, np.ones(len(Q))] @ H.T; return q[:, :2] / q[:, 2:3]


def ecc(T, I, M, H, crit, g):
    """OpenCV 5 : masque du GABARIT via findTransformECCWithMask ; OpenCV 4 : findTransformECC (masque = entrée)."""
    if hasattr(cv2, 'findTransformECCWithMask'):
        return cv2.findTransformECCWithMask(T, I, M, np.ones(I.shape, np.uint8), H, cv2.MOTION_HOMOGRAPHY, crit, g)
    return cv2.findTransformECC(T, I, H, cv2.MOTION_HOMOGRAPHY, crit, None, g)


def cr(u, v):
    return u[0] * v[1] - u[1] * v[0]


def area(Q):
    x, y = Q[:, 0], Q[:, 1]; return 0.5 * (x @ np.roll(y, -1) - y @ np.roll(x, -1))


def main():
    a = sys.argv
    if len(a) < 4: sys.exit(__doc__)
    video, spec, outp = a[1], json.load(open(a[2], encoding='utf-8')), a[3]
    chk = a[a.index('--check') + 1] if '--check' in a else None
    P = spec.get('pad', 300); els = spec['elements']
    lo = min(min(e['f0'], e['anchor']) for e in els); hi = max(e['f1'] for e in els)
    cap = cv2.VideoCapture(video); cap.set(cv2.CAP_PROP_POS_FRAMES, lo); G = {}
    for f in range(lo, hi + 1):
        ok, im = cap.read()
        if not ok: break
        G[f] = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    padc = {}
    def pad(f):
        if f not in padc:
            if len(padc) > 40: padc.clear()
            padc[f] = cv2.copyMakeBorder(G[f], P, P, P, P, cv2.BORDER_CONSTANT, value=255).astype(np.float32)
        return padc[f]
    out = {'elements': {}}
    crit = (cv2.TERM_CRITERIA_COUNT | cv2.TERM_CRITERIA_EPS, 60, 1e-5)
    for e in els:
        A = e['anchor']; m = e.get('margin', 16)
        Q = np.array(e['quad'], float) if 'quad' in e else anchor_quad(G[A], e['seed'], e.get('thr', 10))
        x0, y0 = np.floor(Q.min(0) - m).astype(int); x1, y1 = np.ceil(Q.max(0) + m).astype(int)
        T0 = pad(A)[y0 + P:y1 + P, x0 + P:x1 + P].copy(); th, tw = T0.shape
        Qt = Q - [x0, y0]; mask = np.zeros((th, tw), np.uint8)
        cv2.fillPoly(mask, [np.round(Qt).astype(np.int32)], 1); mask = cv2.dilate(mask, np.ones((2 * m // 2 + 1,) * 2, np.uint8))
        Hh, Ww = G[A].shape; yy, xx = np.mgrid[y0:y1, x0:x1]   # partie HORS CADRE à l'ancre exclue du gabarit
        mask &= ((xx >= 0) & (xx < Ww) & (yy >= 0) & (yy < Hh)).astype(np.uint8)
        ink0 = float(((255 - T0) * mask).sum()) / max(1, mask.sum())
        H0 = np.array([[1, 0, x0 + P], [0, 1, y0 + P], [0, 0, 1]], np.float64)
        res = {A: (H0, 1.0)}
        for step in (1, -1):
            T = T0.copy(); H = H0.copy(); Hp = H0.copy(); fails = 0; f = A + step
            while e['f0'] <= f <= e['f1'] and f in G:
                I = pad(f); Hi = H @ np.linalg.inv(Hp) @ H if fails == 0 else H   # vitesse constante
                best = None
                for Hstart in (Hi, H):
                    Hc = Hstart.copy(); cc = -1
                    try:
                        for s in (0.25, 0.5, 1.0):
                            S = np.diag([s, s, 1.0]); Ts = cv2.resize(T, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
                            Is = cv2.resize(I, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
                            Ms = cv2.resize(mask, (Ts.shape[1], Ts.shape[0]), interpolation=cv2.INTER_NEAREST)
                            Hs = (S @ Hc @ np.linalg.inv(S)).astype(np.float32)
                            cc, Hs = ecc(Ts, Is, Ms, Hs, crit, 5 if s < 1 else 3)
                            Hc = np.linalg.inv(S) @ Hs.astype(np.float64) @ S
                    except cv2.error:
                        cc = -1
                    Qf = proj(Hc, Qt); ar = area(Qf) / area(Qt)
                    sane = 0.15 < ar < 6 and all(cr(Qf[(i + 1) % 4] - Qf[i], Qf[(i + 2) % 4] - Qf[(i + 1) % 4]) > 0 for i in range(4))
                    if sane and (best is None or cc > best[1]): best = (Hc, cc)
                if best is None or best[1] < e.get('min_cc', 0.55):
                    fails += 1; res[f] = None
                    if fails >= e.get('max_fails', 4): break
                    f += step; continue
                Hp, H = (H if fails == 0 else best[0]), best[0]; fails = 0; res[f] = (H, best[1])
                if best[1] < 0.95:   # apparence qui change : gabarit rafraîchi, même géométrie
                    Tw = cv2.warpPerspective(I, H, (tw, th), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderValue=255)
                    T = np.where(mask > 0, 0.5 * T + 0.5 * Tw, T).astype(np.float32)
                f += step
        fr = {}
        for f in range(e['f0'], e['f1'] + 1):
            r = res.get(f)
            if not r: fr[f] = None; continue
            H, cc = r; Iw = cv2.warpPerspective(pad(f), H, (tw, th), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderValue=255)
            ink = float(((255 - Iw) * mask).sum()) / max(1, mask.sum())
            fr[f] = {'quad': np.round(proj(H, Qt) - P, 2).tolist(), 'cc': round(float(cc), 3), 'alpha': round(ink / max(ink0, 1e-6), 3)}
        ok = sum(1 for v in fr.values() if v)
        print(f"{e['id']}: ancre {A}, {ok}/{len(fr)} images suivies, cc min {min((v['cc'] for v in fr.values() if v), default=0):.2f}")
        out['elements'][e['id']] = {'anchor_quad': np.round(Q, 2).tolist(), 'frames': fr}
        if chk:
            os.makedirs(chk, exist_ok=True); fs = list(range(e['f0'], e['f1'] + 1)); pick = [fs[int(i * (len(fs) - 1) / 7)] for i in range(8)]
            tiles = []
            for f in pick:
                im = cv2.cvtColor(G[f], cv2.COLOR_GRAY2BGR)
                if fr[f]: cv2.polylines(im, [np.round(np.array(fr[f]['quad'])).astype(np.int32)], True, (255, 0, 255), 2)
                cv2.putText(im, f'{f} {fr[f]["cc"] if fr[f] else "-"}', (10, 50), 0, 1.4, (255, 0, 255), 3); tiles.append(cv2.resize(im, (240, 427)))
            cv2.imwrite(os.path.join(chk, e['id'] + '.png'), np.hstack(tiles))
    json.dump(out, open(outp, 'w', encoding='utf-8'))


if __name__ == '__main__':
    main()
