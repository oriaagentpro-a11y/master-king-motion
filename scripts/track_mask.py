"""Box of whatever differs from a flat background, on every frame (3D object, icon, phone, sparkle on a plain set).

Usage: python3 track_mask.py <video> <f0> <f1> <x,y,w,h roi> <out.json> [--bg HEX|auto] [--tol 18] [--key name]
                             [--min-area 20] [--largest]
Pixels of the ROI farther than --tol from the background colour (auto = modal colour of the ROI on the first frame)
form the mask; the union box of components >= --min-area (or only the largest with --largest) is recorded as
[left, top, width, height], the same format as track_textbox.py, so track_fit.py reads it with --key.
Also stored: the mask area (key + "_area") — a proxy for scale when the object turns (width alone lies).
"""
import sys, os, json
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mkcommon as mk  # noqa: E402


def main():
    a = sys.argv
    if len(a) < 6:
        sys.exit(__doc__)
    video, f0, f1 = a[1], int(a[2]), int(a[3])
    x, y, w, h = map(int, a[4].split(',')); out = a[5]
    key = mk.arg(a, 'key', 'obj'); tol = mk.arg(a, 'tol', 18, float); mn = mk.arg(a, 'min-area', 20, int); bg = mk.arg(a, 'bg', 'auto')
    cap = cv2.VideoCapture(video); cap.set(cv2.CAP_PROP_POS_FRAMES, f0)
    B = None; rows, areas = {}, {}
    for f in range(f0, f1 + 1):
        ok, im = cap.read()
        if not ok:
            break
        roi = im[y:y + h, x:x + w].astype(np.float32)
        if B is None:
            if bg == 'auto':
                q = (roi.reshape(-1, 3) // 4) * 4; v, c = np.unique(q, axis=0, return_counts=True); B = v[c.argmax()] + 2
            else:
                B = np.array([int(bg[i:i + 2], 16) for i in (4, 2, 0)], np.float32)
        m = (np.abs(roi - B).max(axis=2) > tol).astype(np.uint8)
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
        n, lab, st, _ = cv2.connectedComponentsWithStats(m)
        comps = [s for s in st[1:] if s[4] >= mn]
        if not comps:
            continue
        if '--largest' in a:
            comps = [max(comps, key=lambda s: s[4])]
        x0 = min(c[0] for c in comps); y0 = min(c[1] for c in comps)
        x1 = max(c[0] + c[2] for c in comps); y1 = max(c[1] + c[3] for c in comps)
        rows[f] = [int(x + x0), int(y + y0), int(x1 - x0), int(y1 - y0)]; areas[f] = int(sum(c[4] for c in comps))
    data = json.load(open(out)) if os.path.exists(out) else {}
    data[key] = rows; data[key + '_area'] = areas
    json.dump(data, open(out, 'w'))
    print(f'{key}: {len(rows)} images (fond {mk.hexc(B[::-1]) if B is not None else "?"}) -> {out}')


if __name__ == '__main__':
    main()
