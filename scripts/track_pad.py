"""Agrandit le canevas d'une piste d'homographie (marge autour de la surface) : les zones qui n'entrent dans le cadre
qu'à d'autres images (panoramique sur une interface) sont alors couvertes par la planche médiane (règle 96).

Usage: python3 track_pad.py track.json out.json --pad 300 [--padx 400 --pady 200] | --auto 736,414 [--frames a-b]
--auto W,H : marge EXACTE = boîte englobante, dans le canevas, de toutes les images (W x H) de la plage (rien de trop).
Coins du nouveau canevas = homographie de chaque image (ancien canevas -> image) appliquée au rectangle agrandi.
Le film pose la planche agrandie avec ces nouveaux coins (même mouvement, plus de bords vides).
"""
import sys, json
import numpy as np
import cv2

sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import mkcommon as mk  # noqa: E402


def main():
    a = sys.argv
    if len(a) < 3:
        sys.exit(__doc__)
    tr = json.load(open(a[1])); p = mk.arg(a, 'pad', 300, float)
    px = mk.arg(a, 'padx', p, float); py = mk.arg(a, 'pady', p, float)
    W, H = tr['W'], tr['H']; can = np.float32([[0, 0], [W, 0], [W, H], [0, H]])
    x0, y0, x1, y1 = -px, -py, W + px, H + py
    if mk.arg(a, 'auto'):
        fw, fh = map(float, mk.arg(a, 'auto').split(',')); pts = []
        rng = None
        if mk.arg(a, 'frames'):
            f0, f1 = map(int, mk.arg(a, 'frames').split('-')); rng = (f0, f1)
        for f, c in tr['corners'].items():
            if not c or (rng and not rng[0] <= int(f) <= rng[1]):
                continue
            Hi = cv2.getPerspectiveTransform(np.float32(c), can)
            pts.append(cv2.perspectiveTransform(np.float32([[0, 0], [fw, 0], [fw, fh], [0, fh]]).reshape(-1, 1, 2), Hi).reshape(-1, 2))
        P = np.vstack(pts); x0, y0 = np.floor(P.min(0) - 4); x1, y1 = np.ceil(P.max(0) + 4)
    big = np.float32([[x0, y0], [x1, y0], [x1, y1], [x0, y1]])
    out = dict(tr); out['W'] = float(x1 - x0); out['H'] = float(y1 - y0); out['pad'] = [float(-x0), float(-y0)]; C = {}
    for f, c in tr['corners'].items():
        if not c:
            C[f] = None; continue
        Hm = cv2.getPerspectiveTransform(can, np.float32(c))
        C[f] = [[round(float(x), 2), round(float(y), 2)] for x, y in cv2.perspectiveTransform(big.reshape(-1, 1, 2), Hm).reshape(-1, 2)]
    out['corners'] = C; out.pop('frames', None)
    json.dump(out, open(a[2], 'w')); print(f'canevas {W:.0f}x{H:.0f} -> {out["W"]:.0f}x{out["H"]:.0f} -> {a[2]}')


if __name__ == '__main__':
    main()
