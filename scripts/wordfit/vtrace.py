"""Formes plates recréées en vecteurs mesurés (points, tirets, anneau, trait, éclats) — aucun pixel de l'original n'est copié :
chaque image, l'encre menthe/blanche est seuillée à 50 %, ses contours deviennent des chemins SVG (couleur pleine mesurée),
puis deux flous sont mesurés : bord (s1) et lueur (s2, intensité g) par moindres carrés sur l'alpha.
Usage : python3 vtrace.py sN id f0 f1 x,y,w,h [--holes holes.json] [--inks wm] [--min 6]
holes.json : {"f" ou "a-b": [[x,y,w,h], ...]} zones exclues (éléments déjà reconstruits : pilule, mots)
Sortie : tracks/sN_vec_id.json {f: {paths: [[ink, d], ...], s1, s2, g}}"""
import sys, json
from fitlib import *
sc, vid, f0, f1 = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]); RX, RY, RW, RH = map(int, sys.argv[5].split(','))
holes = json.load(open(sys.argv[sys.argv.index('--holes') + 1])) if '--holes' in sys.argv else {}
inks = sys.argv[sys.argv.index('--inks') + 1] if '--inks' in sys.argv else 'wm'
mina = float(sys.argv[sys.argv.index('--min') + 1]) if '--min' in sys.argv else 6
def hole_list(f):
    out = []
    for k, v in holes.items():
        a, b = (map(int, k.split('-')) if '-' in k else (int(k), int(k)))
        if a <= f <= b: out += v
    return out
def poly_alpha(polys, W, H, ss=4):
    im = np.zeros((H * ss, W * ss), np.uint8)
    for p in polys:
        cv2.fillPoly(im, [np.round((p + 0.5) * ss - 0.5).astype(np.int32)], 255, lineType=cv2.LINE_AA)
    return cv2.resize(im.astype(np.float64) / 255, (W, H), interpolation=cv2.INTER_AREA)
res = {}
for f in range(f0, f1 + 1):
    roi = [RX, RY, min(RW, 736 - RX), min(RH, 414 - RY)]
    A = {k: alpha(f, roi, k) for k in inks}
    for hx, hy, hw, hh in hole_list(f):
        for k in A: A[k][max(0, hy - RY):max(0, hy + hh - RY), max(0, hx - RX):max(0, hx + hw - RX)] = 0
    paths, core = [], {}
    for k in inks:
        m = (A[k] > 0.5).astype(np.uint8)
        # contour sous-pixel : on trace sur une version agrandie lissée de l'alpha
        up = cv2.resize(A[k], None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC); mu = (up > 0.5).astype(np.uint8)
        cs, hier = cv2.findContours(mu, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
        polys = []
        for i, c in enumerate(cs):
            if cv2.contourArea(c) < mina * 16: continue
            c = cv2.approxPolyDP(c, 1.2, True)[:, 0, :].astype(float) / 4 - 0.375
            polys.append(c)
        core[k] = polys
        for c in polys:
            d = 'M' + ' L'.join(f'{x + RX:.2f} {y + RY:.2f}' for x, y in c) + ' Z'
            paths.append([k, d])
    if not paths: continue
    # flous mesurés sur l'ensemble des encres
    Atot = sum(A.values()); W, H = roi[2], roi[3]
    C0 = np.clip(sum(poly_alpha(core[k], W, H) for k in inks), 0, 1)
    def L(p):
        s1, s2, g = abs(p[0]), abs(p[1]), abs(p[2])
        c = cv2.GaussianBlur(C0, (0, 0), max(s1, .05)); gl = cv2.GaussianBlur(C0, (0, 0), max(s2, .3)) * g
        return float(((np.clip(c + gl * (1 - c), 0, 1) - Atot) ** 2).sum())
    r = minimize(L, [0.6, 6, 0.3], method='Nelder-Mead', options={'maxiter': 400})
    s1, s2, g = map(lambda v: round(abs(float(v)), 3), r.x)
    res[f] = {'paths': paths, 's1': s1, 's2': s2, 'g': min(g, 3.0)}
    print(f, len(paths), 'chemins', s1, s2, g, round(r.fun / max(1, (Atot > .05).sum()), 4), flush=True)
json.dump(res, open(D + f'tracks/{sc}_vec_{vid}.json', 'w'))
