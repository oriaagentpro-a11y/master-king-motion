"""Find a phone SCREEN on every frame as the bright hole inside the dark bezel, and return its 4 corners
(line-fitted, rule 20b) in track_quad.py format, ready for pose_from_quad.py.

Usage: python3 track_screen.py <video> <f0> <f1> <out.json> [--dark 70] [--roi x,y,w,h] [--min-area 800]
                               [--debug dir]
Per frame: dark pixels (luma < --dark) inside the ROI = bezel / body; contours with holes (RETR_CCOMP); the largest
hole of the largest dark component whose shape is a rounded rectangle = the screen. Frames where no screen is
seen (phone from the back, screen hidden) are left out — measure the silhouette there (track_mask).
--debug: writes overlays of the found corners every 5 frames to check by eye (rule 5).
"""
import os as _o, sys as _s; _s.path.insert(0, _o.path.dirname(_o.path.abspath(__file__))); import _mkpy  # noqa: E401,E702,F401  (bon Python + PATH)
import sys, os, json
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mkcommon as mk  # noqa: E402
from track_quad import quad_lines, order  # noqa: E402


def main():
    a = sys.argv
    if len(a) < 5:
        sys.exit(__doc__)
    video, f0, f1, out = a[1], int(a[2]), int(a[3]), a[4]
    dk = mk.arg(a, 'dark', 70, float); mn = mk.arg(a, 'min-area', 800, int); dbg = mk.arg(a, 'debug')
    cap = cv2.VideoCapture(video); cap.set(cv2.CAP_PROP_POS_FRAMES, f0)
    roi = list(map(int, mk.arg(a, 'roi', '0,0,100000,100000').split(',')))
    rows = {}
    if dbg:
        os.makedirs(dbg, exist_ok=True)
    for f in range(f0, f1 + 1):
        ok, im = cap.read()
        if not ok:
            break
        g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
        m = (g < dk).astype(np.uint8)
        keep = np.zeros_like(m); x, y, w, h = roi; keep[y:y + h, x:x + w] = 1; m &= keep
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
        cs, hier = cv2.findContours(m, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
        if hier is None:
            continue
        hier = hier[0]; best = None
        for i, c in enumerate(cs):
            if hier[i][3] != -1:       # holes: parent = the dark component
                ar = cv2.contourArea(c)
                if ar < mn:
                    continue
                rect = cv2.minAreaRect(c); fill = ar / max(rect[1][0] * rect[1][1], 1)
                if fill < 0.80:        # a screen is a (rounded) rectangle
                    continue
                if best is None or ar > best[0]:
                    best = (ar, c)
        if best is None:
            continue
        q = np.asarray(quad_lines(best[1]), float)
        q = order(q)
        rows[f] = {'quad': np.round(q, 2).tolist(), 'center': np.round(q.mean(0), 2).tolist(), 'area': int(best[0])}
        if dbg and (f - f0) % 5 == 0:
            o = im.copy(); cv2.polylines(o, [q.astype(np.int32).reshape(-1, 1, 2)], True, (0, 0, 255), 1)
            for k, p in enumerate(q):
                cv2.circle(o, tuple(int(v) for v in p), 3, (0, 255, 0) if k == 0 else (255, 0, 0), -1)
            cv2.imwrite(os.path.join(dbg, f'f{f:05d}.png'), o)
    json.dump({'rows': rows}, open(out, 'w'))
    print(f'écran trouvé sur {len(rows)}/{f1 - f0 + 1} images -> {out}')


if __name__ == '__main__':
    main()
