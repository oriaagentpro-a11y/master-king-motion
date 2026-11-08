# Apparence des pièces mesurée (couleurs des dégradés CSS) + logos blancs vectorisés en coordonnées normalisées.
import json
from fitlib import *
C = json.load(open(D + 'tracks/s5_coins_raw.json'))
def field(f, k, n=14, excl=False):
    e = C[k][str(f)]; o = frame(f); cx, cy, rx, ry = e['cx'], e['cy'], e['w'] / 2, e['h'] / 2
    yy, xx = np.mgrid[0:414, 0:736]; u = (xx + 0.5 - cx) / rx; v = (yy + 0.5 - cy) / ry; r = np.hypot(u, v)
    ok = (o.min(2) < 185) if excl else np.ones((414, 736), bool)
    rad = []
    for i in range(n):
        m = (r >= i / n) & (r < (i + 1) / n) & ok
        if m.sum() == 0: m = (r >= i / n) & (r < (i + 1) / n)
        rad.append(o[m].mean(0)[::-1].tolist())   # RGB
    R = np.zeros_like(o); ri = np.clip((r * n).astype(int), 0, n - 1)
    for i in range(n): R[ri == i] = np.array(rad[i][::-1])
    lin = []
    for j in range(n):
        m = (r < 0.97) & (v >= -1 + 2 * j / n) & (v < -1 + 2 * (j + 1) / n) & ok
        T = o[m].mean(0); Rm = R[m].mean(0); lin.append(np.clip(2 * T - Rm, 0, 255)[::-1].tolist())
    return rad, lin
out = {}
out['glass'] = field(205, 'M')
for k, f in (('L', 225), ('M', 225), ('R', 225)):
    rad, lin = field(f, k, excl=True); e = C[k][str(f)]
    # logo blanc : contour de l'encre blanche (seuil 50 %) dans la face, en coordonnées normalisées
    o = frame(f); x0, y0 = int(e['cx'] - e['w'] / 2), int(e['cy'] - e['h'] / 2); W, H = int(e['w']) + 2, int(e['h']) + 2
    sub = o[y0:y0 + H, x0:x0 + W]; wm = (sub.min(2) > 200).astype(np.float64)
    wa = np.clip((sub.min(2) - 120) / 135, 0, 1)
    yy, xx = np.mgrid[0:H, 0:W]; rr = np.hypot((xx + x0 + .5 - e['cx']) / (e['w'] / 2), (yy + y0 + .5 - e['cy']) / (e['h'] / 2))
    wa[rr > 0.72] = 0
    up = cv2.resize(wa, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC); cs, _ = cv2.findContours((up > 0.5).astype(np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    paths = []
    for c in cs:
        if cv2.contourArea(c) < 40 * 16: continue
        c = cv2.approxPolyDP(c, 1.0, True)[:, 0, :].astype(float) / 4 - 0.375
        nu = (c[:, 0] + x0 + .5 - e['cx']) / (e['w'] / 2); nv = (c[:, 1] + y0 + .5 - e['cy']) / (e['h'] / 2)
        paths.append('M' + ' L'.join(f'{a:.4f} {b:.4f}' for a, b in zip(nu, nv)) + ' Z')
    out[k] = {'rad': rad, 'lin': lin, 'logo': paths}
    print(k, len(paths), 'chemins', [round(c) for c in rad[0]], [round(c) for c in rad[-1]])
json.dump(out, open(D + 'tracks/s5_faces.json', 'w'))
print('glass', [[round(c) for c in x] for x in out['glass'][0]])
