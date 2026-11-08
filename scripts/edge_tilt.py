"""Measure the in-plane TILT of an object (padlock, card, badge) frame by frame from the slope of its BOTTOM edge:
the lowest ink pixel of each column over the central 60 % of the object, fitted with a line.
Positive angle = clockwise (right side lower), the sign CSS `rotation` uses.

Usage: python3 edge_tilt.py ref.mp4 f0 f1 [--dark 130] [--region x0,y0,x1,y1] [--fit t0]
- --dark: the object is darker than this luminance (light background); use --region to exclude other elements.
- --fit t0: fit_easing on the samples from time t0 (s) on.
minAreaRect is NOT used: on a blurred, rounded body it snaps to 0 deg (measured: it returned 0 where the bottom
edge gave +6.7 deg). An eye reading gave -12 deg (WRONG sign) where this tool gave +6.7 deg (rule 56).
"""
import os as _o, sys as _s; _s.path.insert(0, _o.path.dirname(_o.path.abspath(__file__))); import _mkpy  # noqa: E401,E702,F401  (bon Python + PATH)
import sys, os, math
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mkcommon as mk  # noqa: E402
from fit_easing import fit  # noqa: E402


def main():
    a = sys.argv
    if len(a) < 4:
        sys.exit(__doc__)
    ref, f0, f1 = a[1], int(a[2]), int(a[3])
    dark = mk.arg(a, 'dark', 130, int); reg = mk.arg(a, 'region')
    pd = mk.pulldown(ref); D = pd['distinct'] if pd else None; fps = mk.probe(ref)['fps']
    c = cv2.VideoCapture(ref); pts = []
    for f in range(f0, f1 + 1):
        if D is not None and f not in D:
            continue
        c.set(cv2.CAP_PROP_POS_FRAMES, f); ok, im = c.read()
        if not ok:
            break
        g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).astype(float); ox = oy = 0
        if reg:
            x0, y0, x1, y1 = [int(v) for v in reg.split(',')]; g = g[y0:y1, x0:x1]; ox, oy = x0, y0
        m = g < dark; cols = np.where(m.sum(0) > 15)[0]
        if len(cols) < 30:
            print(f, '-'); continue
        a0, a1 = cols.min(), cols.max(); xs = np.arange(int(a0 + 0.2 * (a1 - a0)), int(a1 - 0.2 * (a1 - a0)))
        bot = np.array([np.where(m[:, x])[0].max() for x in xs]); k, _ = np.polyfit(xs, bot, 1)
        ang = math.degrees(math.atan(k)); t = (pd['offset'] + D.index(f) / pd['true_fps']) if D is not None else f / fps
        pts.append((t, ang)); print(f, f'{t:.3f}s', 'inclinaison', round(ang, 1), 'largeur', int(a1 - a0))
    if mk.arg(a, 'fit') and pts:
        P = np.array([p for p in pts if p[0] >= float(mk.arg(a, 'fit'))])
        print('ajustement', fit(P[:, 0], P[:, 1]))


if __name__ == '__main__':
    main()
