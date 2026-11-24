"""Suivi par COULEUR de plusieurs objets qui se chevauchent (cartes empilées, pilules volantes), image par image.

Usage: python3 color_blobs.py ref.mp4 f0 f1 spec.json out.json [--distinct]
spec.json = {"roi": [x, y, w, h] (optionnel),
             "objects": [{"id": "jaune", "hex": "FFDE3A", "tol": 40, "min_area": 300}, ...]}
Pour chaque image et chaque objet : pixels à moins de `tol` (distance RGB) de sa couleur, ouverture 3x3, plus grande
composante → centroïde (cx, cy), rectangle minimal (w, h, angle en degrés, w >= h), aire, boîte englobante, et
« visible » = aire / aire max de l'objet sur la plage (une carte cachée par une autre a une aire qui baisse : sa
position reste mesurée sur la partie visible ; ne pas lire son échelle là où visible < 0,8).
--distinct : saute les images dupliquées d'une référence en pulldown (mk.pulldown), règle 52.
Sortie : {"fps", "objects": {id: {frame: {cx, cy, w, h, angle, area, bbox, visible} | null}}}
Ensuite : `fit_easing.py` / `track_fit.py` sur cx, cy, angle, w pour l'ease, le départ et la durée de chaque objet.
Cas réel (Monniz, réf. A f190-207 et f284-300) : 4 cartes empilées et 6 pilules en 3D qui se masquent ; la position
et l'ordre d'arrivée se lisent sans ambiguïté par couleur, alors que track_quad (une couleur à la fois, coins) et
l'homographie ORB échouent quand elles se chevauchent (règle 130).
"""
import os as _o, sys as _s; _s.path.insert(0, _o.path.dirname(_o.path.abspath(__file__))); import _mkpy  # noqa: E401,E702,F401
import sys, os, json
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mkcommon as mk  # noqa: E402


def main():
    a = sys.argv
    if len(a) < 6:
        sys.exit(__doc__)
    video, f0, f1, spec, out = a[1], int(a[2]), int(a[3]), json.load(open(a[4], encoding='utf-8')), a[5]
    V = mk.probe(video)
    skip = set()
    if '--distinct' in a:
        pd = mk.pulldown(video)
        if pd:
            skip = set(range(f0, f1 + 1)) - set(pd['distinct'])
    roi = spec.get('roi')
    cap = cv2.VideoCapture(video); cap.set(cv2.CAP_PROP_POS_FRAMES, f0)
    res = {o['id']: {} for o in spec['objects']}
    k = np.ones((3, 3), np.uint8)
    for f in range(f0, f1 + 1):
        ok, im = cap.read()
        if not ok:
            break
        if f in skip:
            continue
        x0 = y0 = 0
        if roi:
            x0, y0, w, h = roi; im = im[y0:y0 + h, x0:x0 + w]
        rgb = im[:, :, ::-1].astype(np.int32)
        for o in spec['objects']:
            c = np.array([int(o['hex'][i:i + 2], 16) for i in (0, 2, 4)])
            m = (np.sqrt(((rgb - c) ** 2).sum(2)) < o.get('tol', 40)).astype(np.uint8)
            m = cv2.morphologyEx(m, cv2.MORPH_OPEN, k)
            n, lab, st, cen = cv2.connectedComponentsWithStats(m, 8)
            if n <= 1:
                res[o['id']][f] = None; continue
            i = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
            area = int(st[i, cv2.CC_STAT_AREA])
            if area < o.get('min_area', 300):
                res[o['id']][f] = None; continue
            pts = np.column_stack(np.where(lab == i))[:, ::-1].astype(np.float32)
            (rx, ry), (rw, rh), ang = cv2.minAreaRect(pts)
            if rw < rh:
                rw, rh, ang = rh, rw, ang + 90
            ang = ((ang + 90) % 180) - 90
            bx, by, bw, bh = (int(v) for v in st[i, :4])
            res[o['id']][f] = {'cx': round(float(cen[i][0]) + x0, 2), 'cy': round(float(cen[i][1]) + y0, 2),
                               'w': round(float(rw), 2), 'h': round(float(rh), 2), 'angle': round(float(ang), 2),
                               'area': area, 'bbox': [bx + x0, by + y0, bw, bh]}
    for oid, tab in res.items():
        mx = max([v['area'] for v in tab.values() if v] or [1])
        for v in tab.values():
            if v:
                v['visible'] = round(v['area'] / mx, 3)
    mk.save_json({'fps': V['fps'], 'source': video, 'frames': [f0, f1], 'objects': res}, out)
    for oid, tab in res.items():
        seen = [f for f, v in tab.items() if v]
        print(f'{oid}: {len(seen)} images' + (f' ({min(seen)}-{max(seen)})' if seen else ''))
    print('->', out)


if __name__ == '__main__':
    main()
