"""Suivi EXACT de formes sur fond uni, image par image : rectangle orienté, boîte, CONTOUR et couleur (règle 138).
Pour décalquer à l'identique une référence « UI qui flotte sur fond blanc » : chaque carte, pilule, bulle, tache liquide,
vague est suivie séparément et rejouée 1:1 (même image, même rectangle, même contour), puis lissée légèrement.

Usage: python3 comp_track.py ref.mp4 spec.json out.json
spec = {"bg": "FFFFFF", "bg_tol": 12, "close": 9,                      # pixels de fond = à moins de bg_tol du fond
        "elements": [{"id": "pilule", "f0": 0, "f1": 41, "seed": [355, 558],   # point dans l'élément à l'image f0
                      "hex": null | "55E107", "tol": 50,              # couleur imposée (sinon : tout ce qui n'est pas fond)
                      "roi": [x, y, w, h] | null, "min_area": 300, "contour": true, "eps": 1.5, "union": false}, ...]}
Par image : composantes (masque fermé de `close` px) ; l'élément = la composante contenant / la plus proche du centre
de l'image précédente (identité stable) ; sorties : bbox, minAreaRect (cx, cy, w, h, angle, w >= h), aire, couleur
moyenne, contour simplifié (approxPolyDP eps px) si demandé. Sortie : {"fps", "elements": {id: {f: {...} | null}}}
Lissage pour l'adaptation (règle 110) : `smooth_tracks.py` ou le lissage du film (Savitzky-Golay 5-7 images).
"""
import os as _o, sys as _s; _s.path.insert(0, _o.path.dirname(_o.path.abspath(__file__))); import _mkpy  # noqa: E401,E702,F401
import sys, os, json
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mkcommon as mk  # noqa: E402


def hexbgr(h):
    return np.array([int(h[i:i + 2], 16) for i in (4, 2, 0)])


def main():
    a = sys.argv
    if len(a) < 4:
        sys.exit(__doc__)
    video, spec, out = a[1], json.load(open(a[2], encoding='utf-8')), a[3]
    V = mk.probe(video); bg = hexbgr(spec.get('bg', 'FFFFFF')); btol = spec.get('bg_tol', 12); ck = spec.get('close', 9)
    els = spec['elements']; f0 = min(e['f0'] for e in els); f1 = max(e['f1'] for e in els)
    res = {e['id']: {} for e in els}; last = {e['id']: np.array(e['seed'], float) for e in els}
    cap = cv2.VideoCapture(video); cap.set(cv2.CAP_PROP_POS_FRAMES, f0)
    for f in range(f0, f1 + 1):
        ok, im = cap.read()
        if not ok:
            break
        diff = np.abs(im.astype(int) - bg).max(2)
        base = (diff > btol).astype(np.uint8)
        for e in els:
            if not (e['f0'] <= f <= e['f1']):
                continue
            m = base if not e.get('hex') else (np.abs(im.astype(int) - hexbgr(e['hex'])).max(2) <= e.get('tol', 50)).astype(np.uint8)
            if e.get('roi'):
                x, y, w, h = e['roi']; k = np.zeros_like(m); k[y:y + h, x:x + w] = 1; m = m & k
            if ck:
                m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((ck, ck), np.uint8))
            n, lab, st, cen = cv2.connectedComponentsWithStats(m, 8)
            cands = [i for i in range(1, n) if st[i, 4] >= e.get('min_area', 300)]
            if not cands:
                res[e['id']][f] = None; continue
            if e.get('union'):   # élément blanc sur blanc (fenêtre) : boîte = union de tout ce qu'il contient
                bx = np.array([st[j, :4] for j in cands]); x0, y0 = bx[:, 0].min(), bx[:, 1].min(); x1, y1 = (bx[:, 0] + bx[:, 2]).max(), (bx[:, 1] + bx[:, 3]).max()
                res[e['id']][f] = {'bbox': [int(x0), int(y0), int(x1 - x0), int(y1 - y0)], 'cx': float(x0 + x1) / 2, 'cy': float(y0 + y1) / 2,
                                   'w': float(x1 - x0), 'h': float(y1 - y0), 'angle': 0.0, 'area': int(sum(st[j, 4] for j in cands))}; continue
            p = last[e['id']]; px, py = int(np.clip(p[0], 0, V['w'] - 1)), int(np.clip(p[1], 0, V['h'] - 1))
            inside = [i for i in cands if lab[py, px] == i]
            i = inside[0] if inside else min(cands, key=lambda j: np.linalg.norm(cen[j] - p))
            comp = (lab == i).astype(np.uint8)
            pts = np.column_stack(np.where(comp))[:, ::-1].astype(np.float32)
            (cx, cy), (rw, rh), ang = cv2.minAreaRect(pts)
            if rw < rh:
                rw, rh, ang = rh, rw, ang + 90
            ang = ((ang + 90) % 180) - 90
            col = im[comp > 0].mean(0)[::-1]
            r = {'bbox': [int(v) for v in st[i, :4]], 'cx': round(float(cx), 2), 'cy': round(float(cy), 2), 'w': round(float(rw), 2),
                 'h': round(float(rh), 2), 'angle': round(float(ang), 2), 'area': int(st[i, 4]), 'color': '#%02X%02X%02X' % tuple(int(c) for c in col)}
            if e.get('contour', False):
                cs, _ = cv2.findContours(comp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
                c = max(cs, key=cv2.contourArea); c = cv2.approxPolyDP(c, e.get('eps', 1.5), True).reshape(-1, 2)
                r['contour'] = c.tolist()
            res[e['id']][f] = r; last[e['id']] = np.array(cen[i], float)
    mk.save_json({'fps': V['fps'], 'source': video, 'elements': res}, out)
    for k, t in res.items():
        seen = [f for f, v in t.items() if v]
        print(f'{k}: {len(seen)} images' + (f' ({min(seen)}-{max(seen)})' if seen else ''))


if __name__ == '__main__':
    main()
