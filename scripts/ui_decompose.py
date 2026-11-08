"""Decompose an app screenshot into animatable layers: blocks (cards, bars, buttons), then the pieces inside them
(icons, labels, numbers), each cropped to its own PNG with its position, so the UI can be rebuilt and animated
piece by piece in the film (cards that slide in, icons that pop one by one, numbers that count).

Usage: python3 ui_decompose.py <screenshot.png> <out_dir> [--tol 14] [--min 0.0006] [--depth 2] [--key-bg]
                               [--crop-status 0.055] [--scale 1]
- level 1: regions that differ from the screen's background (flat colour, measured per area) = blocks
- level 2: inside each block, the same on the block's own background = elements (icons, texts, buttons)
- --key-bg: elements get an alpha channel (their block background keyed out, soft edge) -> icons float freely
- --crop-status: removes the phone status bar (top share of the height) — rebuild it in code (time, battery)
Writes out_dir/layers/*.png, out_dir/layout.json (boxes in pixels AND normalised to the screen, parent, bg colour,
kind guess: text-like / icon-like / block) and out_dir/overview.png (numbered boxes, to pick what to animate).
Claude then LOOKS at the overview: texts are rebuilt as live text in the brand font (sharper, editable, can be
typed / counted), icons and illustrations are used as cropped layers, cards as rebuilt HTML boxes.
"""
import os as _o, sys as _s; _s.path.insert(0, _o.path.dirname(_o.path.abspath(__file__))); import _mkpy  # noqa: E401,E702,F401  (bon Python + PATH)
import sys, os, json
import numpy as np
import cv2
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mkcommon as mk  # noqa: E402


def modal(img):
    q = (img.reshape(-1, 3) // 4) * 4
    v, c = np.unique(q, axis=0, return_counts=True)
    return v[c.argmax()].astype(np.float32) + 2


def regions(img, tol, min_area, bg=None, close=9):
    bg = modal(img) if bg is None else bg
    diff = np.abs(img.astype(np.float32) - bg).max(axis=2)
    m = (diff > tol).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((close, close), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(m)
    out = []
    H, W = img.shape[:2]
    for i in range(1, n):
        x, y, w, h, a = st[i]
        if a < min_area * W * H or (w >= W - 2 and h >= H - 2):
            continue
        out.append((int(x), int(y), int(w), int(h)))
    return out, bg


def kind(crop, w, h):
    g = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
    e = cv2.Canny(g, 60, 160)
    ar = w / max(h, 1)
    cols = (e > 0).any(axis=0).astype(int)
    runs = int(np.sum(np.diff(cols) == 1))
    if ar > 2.2 and runs >= 4:
        return 'texte'
    if 0.6 <= ar <= 1.6:
        return 'icône'
    return 'bloc'


def main():
    a = sys.argv
    if len(a) < 3:
        sys.exit(__doc__)
    src, out = a[1], a[2]
    tol = mk.arg(a, 'tol', 14, float); mn = mk.arg(a, 'min', 0.0006, float); depth = mk.arg(a, 'depth', 2, int)
    key = '--key-bg' in a; cs = mk.arg(a, 'crop-status', 0.0, float)
    img = np.array(Image.open(src).convert('RGB'))
    H0 = img.shape[0]; top = int(H0 * cs)
    img = img[top:]
    H, W = img.shape[:2]
    os.makedirs(os.path.join(out, 'layers'), exist_ok=True)
    items = []
    # level 1 on horizontal bands: big screens have several background colours (header, body) -> measure per band
    l1, bg0 = regions(img, tol, mn * 4, close=15)
    if not l1:
        l1 = [(0, 0, W, H)]
    for bi, (x, y, w, h) in enumerate(sorted(l1, key=lambda b: (b[1], b[0]))):
        blk = img[y:y + h, x:x + w]
        bid = f'b{bi:02d}'
        bbg = modal(blk)
        items.append({'id': bid, 'parent': None, 'level': 1, 'box': [x, y + top, w, h], 'bg': mk.hexc(bbg), 'kind': 'bloc'})
        Image.fromarray(blk).save(os.path.join(out, 'layers', f'{bid}.png'))
        if depth < 2:
            continue
        l2, _ = regions(blk, tol, mn, bg=bbg, close=5)
        for ei, (ex, ey, ew, eh) in enumerate(sorted(l2, key=lambda b: (b[1] // 12, b[0]))):
            if ew * eh > 0.85 * w * h:
                continue
            pad = 3
            x0, y0 = max(0, ex - pad), max(0, ey - pad); x1, y1 = min(w, ex + ew + pad), min(h, ey + eh + pad)
            crop = blk[y0:y1, x0:x1]
            eid = f'{bid}_e{ei:02d}'
            rgba = Image.fromarray(crop).convert('RGBA')
            if key:
                d = np.abs(crop.astype(np.float32) - bbg).max(axis=2)
                al = np.clip((d - tol * 0.5) / (tol * 1.5), 0, 1)
                al = cv2.GaussianBlur(al, (0, 0), 0.6)
                arr = np.array(rgba); arr[..., 3] = (al * 255).astype(np.uint8); rgba = Image.fromarray(arr)
            rgba.save(os.path.join(out, 'layers', f'{eid}.png'))
            items.append({'id': eid, 'parent': bid, 'level': 2, 'box': [x + x0, y + y0 + top, x1 - x0, y1 - y0], 'bg': mk.hexc(bbg),
                          'kind': kind(crop, ex and ew or ew, eh)})
    for it in items:
        x, y, w, h = it['box']
        it['norm'] = {'cx': round((x + w / 2) / img.shape[1], 5), 'cy': round((y + h / 2) / H0, 5), 'w': round(w / img.shape[1], 5), 'h': round(h / H0, 5)}
    mk.save_json({'source': os.path.abspath(src), 'size': [img.shape[1], H0], 'status_bar_cropped_px': top, 'screen_bg': mk.hexc(bg0),
                  'items': items}, os.path.join(out, 'layout.json'))
    ov = Image.open(src).convert('RGB'); d = ImageDraw.Draw(ov)
    for it in items:
        x, y, w, h = it['box']; col = (255, 60, 60) if it['level'] == 1 else (40, 160, 255)
        d.rectangle([x, y, x + w, y + h], outline=col, width=3 if it['level'] == 1 else 2)
        d.text((x + 3, y + 2), it['id'].split('_')[-1], fill=col)
    ov.save(os.path.join(out, 'overview.png'))
    n1 = sum(i['level'] == 1 for i in items)
    print(f"{n1} blocs, {len(items) - n1} éléments -> {out}/layout.json, layers/, overview.png")


if __name__ == '__main__':
    main()
