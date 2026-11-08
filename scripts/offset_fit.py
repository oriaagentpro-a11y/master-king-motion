"""Sub-pixel correction of rebuilt elements against the original, on one (held) frame (règle 91).

Usage: python3 offset_fit.py ref.mp4 ref_frame copy.mp4 copy_frame boxes.json [--blur 0,0.4,0.7] [--range 2] [--step 0.25]
boxes.json = {"The": [x, y, w, h], ...}   (regions in the 736x414 frame; a margin of 4 px is added)
For every region, the copy is shifted by (dx, dy) (and optionally blurred) and compared with the original by SSIM;
prints and returns the best {id: [dx, dy, blur, ssim_before, ssim_after]}. Threshold-measured ink boxes are often
~0.5-1 px off (anti-aliased edges, pixel index vs pixel centre): apply the corrections in the scene (as a constant
translate on each element) and re-measure the whole scene with compare.py.
"""
import sys, json
import cv2
import numpy as np
from skimage.metrics import structural_similarity as ssim

sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import mkcommon as mk  # noqa: E402


def frame(path, f):
    c = cv2.VideoCapture(path); c.set(cv2.CAP_PROP_POS_FRAMES, f); ok, im = c.read(); return im


def main():
    a = sys.argv
    if len(a) < 6:
        sys.exit(__doc__)
    X, Y = frame(a[1], int(a[2])), frame(a[3], int(a[4])); B = json.load(open(a[5]))
    blurs = [float(v) for v in mk.arg(a, 'blur', '0').split(',')]; R = mk.arg(a, 'range', 2.0, float); st = mk.arg(a, 'step', 0.25, float)
    gx = cv2.cvtColor(X, cv2.COLOR_BGR2GRAY); res = {}
    for k, (x, y, w, h) in B.items():
        x0, y0, x1, y1 = max(0, x - 4), max(0, y - 4), min(X.shape[1], x + w + 4), min(X.shape[0], y + h + 4)
        ref = gx[y0:y1, x0:x1]; best = None
        base = ssim(ref, cv2.cvtColor(Y, cv2.COLOR_BGR2GRAY)[y0:y1, x0:x1])
        for bl in blurs:
            Yb = cv2.GaussianBlur(Y, (0, 0), bl) if bl else Y
            for dx in np.arange(-R, R + 1e-6, st):
                for dy in np.arange(-R, R + 1e-6, st):
                    Z = cv2.warpAffine(Yb, np.float32([[1, 0, dx], [0, 1, dy]]), (Y.shape[1], Y.shape[0]), flags=cv2.INTER_LINEAR)
                    s = ssim(ref, cv2.cvtColor(Z, cv2.COLOR_BGR2GRAY)[y0:y1, x0:x1])
                    if best is None or s > best[3]:
                        best = [round(float(dx), 2), round(float(dy), 2), bl, round(float(s), 4)]
        res[k] = [best[0], best[1], best[2], round(float(base), 4), best[3]]
        print(f"{k:12s} dx {best[0]:+.2f} dy {best[1]:+.2f} flou {best[2]}  SSIM {base:.3f} -> {best[3]:.3f}")
    if mk.arg(a, 'json'):
        json.dump(res, open(mk.arg(a, 'json'), 'w'), indent=1)


if __name__ == '__main__':
    main()
