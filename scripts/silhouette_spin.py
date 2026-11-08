"""Measure how fast an object SPINS ON ITSELF (token, coin, logo) from its silhouette: ratio of the short to the long
axis of its outline, frame by frame. Face-on ~1, edge-on ~0; angle = acos(ratio) (a flat disc / tile).

Usage: python3 silhouette_spin.py ref.mp4 f0 f1 --hsv h0,h1,s_min,v_min [--near x,y] [--min-area 30]
- --hsv: OpenCV hue range (0-179) and minimum saturation / value of the object's colour (pick a token with a
  colour no other element has, e.g. the purple one).
- --near x,y: keep the blob closest to this point (follow ONE object when several share the colour); the next
  frame looks near the previous position.
Prints per distinct frame (rule 52): centre, axes, ratio, angle (deg). Spin speed = change of angle between an
edge-on frame (ratio minimum) and the next face-on frame (ratio ~1) divided by the time: 90 deg / dt.
Measured here: purple token A f173 (edge-on, 0.18) -> f181 (face, 0.97) = 90 deg in 0.28 s ~ 320 deg/s.
"""
import sys, os, math
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mkcommon as mk  # noqa: E402


def main():
    a = sys.argv
    if len(a) < 4:
        sys.exit(__doc__)
    ref, f0, f1 = a[1], int(a[2]), int(a[3])
    h0, h1, smin, vmin = [int(v) for v in mk.arg(a, 'hsv').split(',')]
    near = np.array([float(v) for v in mk.arg(a, 'near').split(',')]) if mk.arg(a, 'near') else None
    amin = mk.arg(a, 'min-area', 30, int)
    pd = mk.pulldown(ref); D = pd['distinct'] if pd else None; fps = mk.probe(ref)['fps']
    c = cv2.VideoCapture(ref)
    for f in range(f0, f1 + 1):
        if D is not None and f not in D:
            continue
        c.set(cv2.CAP_PROP_POS_FRAMES, f); ok, im = c.read()
        if not ok:
            break
        hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV).astype(int)
        m = ((hsv[..., 0] >= h0) & (hsv[..., 0] <= h1) & (hsv[..., 1] >= smin) & (hsv[..., 2] >= vmin)).astype(np.uint8)
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        n, lab, st, cen = cv2.connectedComponentsWithStats(m)
        cand = [i for i in range(1, n) if st[i, 4] >= amin]
        if not cand:
            print(f, '-'); continue
        i = min(cand, key=lambda k: math.hypot(*(cen[k] - near))) if near is not None else max(cand, key=lambda k: st[k, 4])
        ys, xs = np.where(lab == i)
        (cx, cy), (w, h), ang = cv2.minAreaRect(np.c_[xs, ys].astype(np.float32))
        r = min(w, h) / max(w, h, 1e-6)
        t = (pd['offset'] + D.index(f) / pd['true_fps']) if D is not None else f / fps
        if near is not None:
            near = np.array([cx, cy])
        print(f, f'{t:.3f}s', 'centre', int(cx), int(cy), 'axes', round(min(w, h), 1), round(max(w, h), 1),
              'rapport', round(r, 2), 'angle', round(math.degrees(math.acos(min(1, r))), 0), 'aire', int(st[i, 4]))


if __name__ == '__main__':
    main()
