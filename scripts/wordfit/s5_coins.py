# Pièces de verre (s5) : ellipse mesurée par image pour chaque pièce (gauche / milieu / droite), 188-243.
import json
from fitlib import *
out = {'L': {}, 'M': {}, 'R': {}}
for f in range(188, 244):
    o = frame(f); B = bgplate(f); dev = np.abs(o - B).max(2)
    m = (dev > 40).astype(np.uint8)
    m[0:110, 250:490] = 0; m[300:414, 250:490] = 0           # « Trade on », « and more » (texte en code)
    if f >= 237:                                           # volet menthe : seulement sous le bord
        pass
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    n, lab, st, cen = cv2.connectedComponentsWithStats(m)
    for i in range(1, n):
        x, y, w, h, a = st[i]
        if a < 150: continue
        cx = x + w / 2; key = 'L' if cx < 260 else ('M' if cx < 480 else 'R')
        cs, _ = cv2.findContours((lab == i).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        c = max(cs, key=cv2.contourArea)
        if len(c) < 6: continue
        (ex, ey), (ew, eh), ea = cv2.fitEllipse(c)
        prev = out[key].get(f)
        if prev is None or a > prev['area']:
            out[key][f] = {'cx': ex, 'cy': ey, 'w': ew, 'h': eh, 'ang': ea, 'area': int(a), 'box': [int(x), int(y), int(w), int(h)]}
    print(f, {k: (round(v[f]['cx']), round(v[f]['cy']), round(v[f]['w']), round(v[f]['h']), round(v[f]['ang'])) for k, v in out.items() if f in v})
json.dump(out, open(D + 'tracks/s5_coins_raw.json', 'w'))
