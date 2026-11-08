"""Affine les coins d'une surface suivie par ALIGNEMENT DIRECT (ECC) sur sa texture propre (règles 91, 95).

Usage: python3 homography_refine.py ref.mp4 track.json texture.png out.json [--frames a-b] [--occ occ.json] [--iters 80]
       [--motion homography|affine|euclid|translation]   (objets ronds / symétriques : affine ou euclid, sinon l'ECC
       trouve des perspectives aberrantes sur un cercle)
- track.json : homography_track.py (coins de départ ; null = interpolé depuis les voisins).
- texture.png: rectify_median.py (même canevas, n'importe quelle échelle).
- occ.json   : quadrilatères qui masquent la surface par image (exclus de l'alignement).
Pour chaque image : on redresse l'image de la référence avec les coins courants, on aligne ce redressé sur la texture
(cv2.findTransformECC, MOTION_HOMOGRAPHY, pyramide 2 niveaux, masque = surface visible), puis on reporte la correction
sur les coins. Bien plus stable que les points ORB quand l'écran est flou, sombre ou partiellement caché ; aucune dérive
puisque chaque image est recalée sur la MÊME texture. Les sauts résiduels (> --jump px) sont remplacés par interpolation.
Sortie : même format que homography_track.py (corners).
"""
import os as _o, sys as _s; _s.path.insert(0, _o.path.dirname(_o.path.abspath(__file__))); import _mkpy  # noqa: E401,E702,F401  (bon Python + PATH)
import sys, json
import numpy as np
import cv2

sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import mkcommon as mk  # noqa: E402


def interp(C, fr):
    ks = sorted(f for f in C if C[f] is not None)
    out = {}
    for f in fr:
        if C.get(f) is not None:
            out[f] = np.float32(C[f]); continue
        lo = max([k for k in ks if k < f], default=None); hi = min([k for k in ks if k > f], default=None)
        if lo is None or hi is None:
            out[f] = np.float32(C[lo if lo is not None else hi]); continue
        u = (f - lo) / (hi - lo); out[f] = np.float32(C[lo]) * (1 - u) + np.float32(C[hi]) * u
    return out


def main():
    a = sys.argv
    if len(a) < 5:
        sys.exit(__doc__)
    src, tr, tex, out = a[1], json.load(open(a[2])), cv2.imread(a[3]), a[4]
    W, H = int(round(tr['W'])), int(round(tr['H']))
    T = cv2.cvtColor(cv2.resize(tex, (W, H), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY).astype(np.float32)
    C = {int(k): v for k, v in tr['corners'].items()}
    fr = sorted(C)
    if mk.arg(a, 'frames'):
        f0, f1 = map(int, mk.arg(a, 'frames').split('-')); fr = [f for f in range(f0, f1 + 1)]
    occ = json.load(open(mk.arg(a, 'occ'))) if mk.arg(a, 'occ') else {}
    iters = mk.arg(a, 'iters', 80, int); jump = mk.arg(a, 'jump', 25.0, float)
    init = interp(C, fr)
    cap = cv2.VideoCapture(src); cap.set(cv2.CAP_PROP_POS_FRAMES, fr[0]); IM = {}
    for f in fr:
        ok, im = cap.read(); IM[f] = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    dst = np.float32([[0, 0], [W, 0], [W, H], [0, H]]); res = {}
    key = mk.arg(a, 'key', int(tr.get('key', fr[len(fr) // 2])), int)
    key = min(max(key, fr[0]), fr[-1])

    def align(f, q0):
        M = cv2.getPerspectiveTransform(np.float32(q0), dst); g = IM[f]
        R = cv2.warpPerspective(g, M, (W, H), flags=cv2.INTER_LINEAR).astype(np.float32)
        m = np.ones(g.shape, np.uint8) * 255
        for p in occ.get(str(f), []):
            cv2.fillPoly(m, [np.array(p, np.int32)], 0)
        mr = cv2.warpPerspective(m, M, (W, H), flags=cv2.INTER_NEAREST, borderValue=0)
        mot = {'homography': cv2.MOTION_HOMOGRAPHY, 'affine': cv2.MOTION_AFFINE, 'euclid': cv2.MOTION_EUCLIDEAN,
               'translation': cv2.MOTION_TRANSLATION}[mk.arg(a, 'motion', 'homography')]
        W0 = np.eye(3, dtype=np.float32) if mot == cv2.MOTION_HOMOGRAPHY else np.eye(2, 3, dtype=np.float32)
        try:
            cc, Wp = cv2.findTransformECC(T, R, W0, mot,
                                         (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, iters, 1e-5), mr, 5)
        except cv2.error:
            return None
        if Wp.shape[0] == 2:
            Wp = np.vstack([Wp, [0, 0, 1]]).astype(np.float32)
        Hc = np.linalg.inv(M) @ Wp          # canevas (texture) -> image
        return cc, cv2.perspectiveTransform(dst.reshape(-1, 1, 2), Hc).reshape(-1, 2)
    for direction in (1, -1):              # depuis l'image clé vers les deux bouts : départ = image voisine recalée
        prev = None
        rng = range(key, fr[-1] + 1) if direction > 0 else range(key - 1, fr[0] - 1, -1)
        if direction < 0:
            prev = res.get(key)
        for f in rng:
            cands = [init[f]] + ([prev] if prev is not None else [])
            best = None
            for q0 in cands:
                r = align(f, q0)
                if r and (best is None or r[0] > best[0]):
                    best = r
            if best is None or best[0] < mk.arg(a, 'mincc', 0.55, float) or (prev is not None and np.abs(best[1] - prev).max() > jump * 3):
                if mk.arg(a, 'debug'):
                    print(f, 'rejeté', None if best is None else round(float(best[0]), 3))
                res[f] = None; continue
            res[f] = best[1]; prev = best[1]
            if mk.arg(a, 'debug'):
                print(f, round(float(best[0]), 3))
    fin = interp({f: (None if v is None else v.tolist()) for f, v in res.items()}, fr)
    tr2 = dict(tr); tr2['corners'] = {str(f): [[round(float(x), 2), round(float(y), 2)] for x, y in fin[f]] for f in fr}
    tr2['refined'] = 'ECC'; tr2['ok'] = [f for f, v in res.items() if v is not None]
    json.dump(tr2, open(out, 'w'))
    print(f'{sum(v is not None for v in res.values())}/{len(fr)} images recalées -> {out}')


if __name__ == '__main__':
    main()
