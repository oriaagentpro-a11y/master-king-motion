"""Rotoscopie vectorielle d'une couleur, image par image, en EXCLUANT des zones qui bougent (règles 91, 93).

Usage: python3 vectorize_masked.py ref.mp4 f0 f1 out.js --color 0,254,182 [--tol 90] [--up 4] [--eps 0.35]
                                    [--exclude-js excl.json] [--var NAME] [--min-area 6]
excl.json = {"<frame>": [[[x, y], [x, y], ...], ...]}   polygones à ignorer à cette image (ex. une étiquette suivie
            à part, un mot de la même couleur rejoué ailleurs). Les pixels exclus ne sont pas tracés.
Sortie : window.NAME = {"<frame>": "M ... Z M ... Z", ...}  (chemins evenodd en pixels de la référence).
Usage : traits animés, pointillés qui se dessinent, comètes, croix, chevrons, éclats : tout ce qui n'est pas une
formule simple. Le résultat est du VECTORIEL (recolorable, lueur en filtre SVG), pas une image extraite.
"""
import os as _o, sys as _s; _s.path.insert(0, _o.path.dirname(_o.path.abspath(__file__))); import _mkpy  # noqa: E401,E702,F401  (bon Python + PATH)
import sys, json
import numpy as np
import cv2

sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import mkcommon as mk  # noqa: E402


def main():
    a = sys.argv
    if len(a) < 5:
        sys.exit(__doc__)
    src, f0, f1, out = a[1], int(a[2]), int(a[3]), a[4]
    col = np.array([int(v) for v in mk.arg(a, 'color', '0,254,182').split(',')][::-1], float)   # RGB -> BGR
    tol = mk.arg(a, 'tol', 90.0, float); up = mk.arg(a, 'up', 4, int); eps = mk.arg(a, 'eps', 0.35, float)
    excl = json.load(open(mk.arg(a, 'exclude-js'))) if mk.arg(a, 'exclude-js') else {}
    minA = mk.arg(a, 'min-area', 6.0, float)
    cap = cv2.VideoCapture(src); cap.set(cv2.CAP_PROP_POS_FRAMES, f0); res = {}
    for f in range(f0, f1 + 1):
        ok, im = cap.read()
        if not ok:
            break
        d = np.sqrt(((im.astype(float) - col) ** 2).sum(2)); A = np.clip(1 - d / tol, 0, 1).astype(np.float32)
        M = np.ones(A.shape, np.uint8)
        for poly in excl.get(str(f), []):
            cv2.fillPoly(M, [np.array(poly, np.int32)], 0)
        A *= M
        Au = cv2.resize(A, (A.shape[1] * up, A.shape[0] * up), interpolation=cv2.INTER_CUBIC)
        B = (Au > 0.5).astype(np.uint8)
        cs, hier = cv2.findContours(B, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
        parts = []
        for c in cs:
            if cv2.contourArea(c) < minA * up * up:
                continue
            ap = cv2.approxPolyDP(c, eps * up, True).reshape(-1, 2) / up
            if len(ap) < 3:
                continue
            parts.append('M' + ' L'.join(f'{x:.2f},{y:.2f}' for x, y in ap) + ' Z')
        res[str(f)] = ' '.join(parts)
    open(out, 'w').write(f"window.{mk.arg(a, 'var', 'VEC')} = " + json.dumps(res) + ';\n')
    print(f'{len(res)} images -> {out}')


if __name__ == '__main__':
    main()
