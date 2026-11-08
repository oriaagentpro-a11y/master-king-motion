"""Follow EVERY element of a reference scene frame by frame as boxes, with stable identities (règle 91).

Usage: python3 box_tracker.py ref.mp4 f0 f1 key_frame spec.json out.json
spec.json = {"classes": {"w": {"min": 140, "maxsat": 60},                      # white-ish ink
                         "m": {"bgr_min": [90, 150, 0], "bgr_max": [255, 255, 120]}},   # an accent colour (BGR bounds)
             "roi": [x0, y0, x1, y1],                                              # optional
             "elements": [{"id": "l", "cls": "w", "box": [x, y, w, h]}, ...],      # boxes AT key_frame
             "dilate": [9, 1],                                                     # optional: track WORDS (boxes grow by kx-1)
             "close": [21, 9]}                                                     # optional: fill text holes in pills/cards
The key frame is a frame where every element is clean and separate. From it the tracker walks backwards
to f0 and forwards to f1. For each frame, the connected components of each class are matched to the
elements by overlap with the element's previous box (IoU, then nearest centre). A component that several
elements fall into (letters merging, motion blur) is split between them in x order, in proportion to their
previous widths; an element with no component is recorded as hidden (null).
Output: {"fps": 25, "tracks": {id: {frame: [x, y, w, h] | null}}, "merged": {id: [frames]}}
The film replays the boxes (engine/mk-boxreplay.js): the copy follows the original box for box; an
adaptation puts the user's element on the SAME track (same frame, same size, same reveal).
"""
import os as _o, sys as _s; _s.path.insert(0, _o.path.dirname(_o.path.abspath(__file__))); import _mkpy  # noqa: E401,E702,F401  (bon Python + PATH)
import sys, json
import cv2
import numpy as np


def masks(im, classes):
    out = {}
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV)
    for k, c in classes.items():
        if 'bgr_min' in c:
            lo, hi = np.array(c['bgr_min']), np.array(c['bgr_max'])
            m = np.all((im >= lo) & (im <= hi), axis=2)
        else:
            m = (im.min(2) >= c.get('min', 140)) & (hsv[..., 1] <= c.get('maxsat', 60))
        out[k] = m.astype(np.uint8)
    return out


def comps(m, roi, min_area):
    n, lab, st, _ = cv2.connectedComponentsWithStats(m)
    res = []
    for s in st[1:]:
        x, y, w, h, a = map(int, s)
        if a < min_area:
            continue
        if roi and (x + w < roi[0] or x > roi[2] or y + h < roi[1] or y > roi[3]):
            continue
        res.append([x, y, w, h])
    return res


def iou(a, b):
    ax1, ay1, bx1, by1 = a[0] + a[2], a[1] + a[3], b[0] + b[2], b[1] + b[3]
    iw, ih = max(0, min(ax1, bx1) - max(a[0], b[0])), max(0, min(ay1, by1) - max(a[1], b[1]))
    inter = iw * ih
    return inter / max(1, a[2] * a[3] + b[2] * b[3] - inter)


def step(prev, cs, max_jump):
    """prev: {id: box}; cs: components -> {id: box|None}, merged ids."""
    owner = {}
    for i, pb in prev.items():
        if pb is None:
            continue
        best, bs = None, 0.0
        for j, c in enumerate(cs):
            s = iou(pb, c)
            if s > bs:
                best, bs = j, s
        if best is None:   # no overlap: nearest centre within max_jump
            pc = (pb[0] + pb[2] / 2, pb[1] + pb[3] / 2); dmin = max_jump
            for j, c in enumerate(cs):
                d = np.hypot(c[0] + c[2] / 2 - pc[0], c[1] + c[3] / 2 - pc[1])
                if d < dmin:
                    best, dmin = j, d
        if best is not None:
            owner.setdefault(best, []).append(i)
    res, merged = {i: None for i in prev}, []
    for j, ids in owner.items():
        c = cs[j]
        if len(ids) == 1:
            res[ids[0]] = c; continue
        ids.sort(key=lambda i: prev[i][0]); tot = sum(prev[i][2] for i in ids); x = c[0]
        for i in ids:
            w = c[2] * prev[i][2] / max(1, tot)
            res[i] = [int(round(x)), c[1], max(1, int(round(w))), c[3]]; x += w; merged.append(i)
    return res, merged


def main():
    a = sys.argv
    if len(a) < 7:
        sys.exit(__doc__)
    src, f0, f1, kf, spec, out = a[1], int(a[2]), int(a[3]), int(a[4]), json.load(open(a[5])), a[6]
    cap = cv2.VideoCapture(src); fps = cap.get(cv2.CAP_PROP_FPS)
    frames = {}
    cap.set(cv2.CAP_PROP_POS_FRAMES, f0)
    for f in range(f0, f1 + 1):
        ok, im = cap.read()
        if not ok:
            break
        ms = masks(im, spec['classes'])
        if spec.get('open'):     # remove thin strokes first (a dashed connector between pills), e.g. [1, 9]
            kx, ky = spec['open']; K = np.ones((ky, kx), np.uint8)
            ms = {k: cv2.morphologyEx(m, cv2.MORPH_OPEN, K) for k, m in ms.items()}
        if spec.get('close'):    # fill the text inside pills / cards (morphological closing), e.g. [21, 9]
            kx, ky = spec['close']; K = np.ones((ky, kx), np.uint8)
            ms = {k: cv2.morphologyEx(m, cv2.MORPH_CLOSE, K) for k, m in ms.items()}
        if spec.get('dilate'):   # merge letters into words (horizontal kernel), e.g. [9, 1]
            kx, ky = spec['dilate']; K = np.ones((ky, kx), np.uint8)
            ms = {k: cv2.dilate(m, K) for k, m in ms.items()}
        frames[f] = {k: comps(m, spec.get('roi'), spec.get('min_area', 4)) for k, m in ms.items()}
    els = spec['elements']; tracks = {e['id']: {} for e in els}; merged = {e['id']: [] for e in els}
    for direction in (-1, 1):
        prev = {e['id']: e['box'] for e in els}
        rng = range(kf, f0 - 1, -1) if direction < 0 else range(kf, f1 + 1)
        for f in rng:
            if f not in frames:
                continue
            res = {}
            for cls in spec['classes']:
                sub = {e['id']: prev[e['id']] for e in els if e['cls'] == cls}
                r, mg = step(sub, frames[f][cls], spec.get('max_jump', 60))
                res.update(r)
                for i in mg:
                    merged[i].append(f)
            for i, b in res.items():
                tracks[i][f] = b
                if b is not None:
                    prev[i] = b
    json.dump({'fps': fps, 'tracks': tracks, 'merged': merged}, open(out, 'w'))
    for i, t in tracks.items():
        vis = sorted(f for f, b in t.items() if b)
        print(f"{i:10s} visible {len(vis)} images ({vis[0] if vis else '-'}–{vis[-1] if vis else '-'}), fusionné {len(set(merged[i]))}")


if __name__ == '__main__':
    main()
