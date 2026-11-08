"""Measure the opacity of a flat-coloured element on every frame (fades, dissolves, blinking).

Usage: python3 track_opacity.py <video> <f0> <f1> <x,y,w,h roi> <ink_hex> <bg_hex> <out.json> [--key name] [--ref-frame F]
Each pixel of the ROI is projected on the line background -> ink colour (0 = background, 1 = ink).
The element's own pixels are those at >= 0.6 on --ref-frame (default: the frame of the ROI where the ink is
the most present); the opacity of a frame is the median projection on those pixels, clipped to 0..1.
Output merged into out.json: {"kind": "opacity", "<key>": {frame: opacity}}. Then:
  track_fit.py out.json ref.mp4 tracks.json --id title --source opacity --key <key> --props opacity
"""
import sys, os, json
import numpy as np
import cv2


def main():
    a = sys.argv
    if len(a) < 8:
        sys.exit(__doc__)
    video, f0, f1 = a[1], int(a[2]), int(a[3])
    x, y, w, h = map(int, a[4].split(','))
    hx = lambda c: np.array([int(c[i:i + 2], 16) for i in (4, 2, 0)], np.float32)  # BGR
    ink, bg, out = hx(a[5]), hx(a[6]), a[7]
    key = a[a.index('--key') + 1] if '--key' in a else 'opacity'
    cap = cv2.VideoCapture(video); cap.set(cv2.CAP_PROP_POS_FRAMES, f0)
    d = ink - bg; dd = float(d @ d) or 1.0
    proj = {}
    for f in range(f0, f1 + 1):
        ok, im = cap.read()
        if not ok:
            break
        roi = im[y:y + h, x:x + w].astype(np.float32)
        proj[f] = np.clip(((roi - bg) @ d) / dd, -0.5, 1.5)
    if not proj:
        sys.exit('aucune image lue')
    rf = int(a[a.index('--ref-frame') + 1]) if '--ref-frame' in a else max(proj, key=lambda k: (proj[k] > 0.6).sum())
    mask = proj[rf] >= 0.6
    if mask.sum() < 10:
        sys.exit(f"l'encre {a[5]} est presque absente de la zone (image {rf}) : vérifier la couleur et la zone")
    rows = {f: round(float(np.clip(np.median(p[mask]), 0, 1)), 4) for f, p in proj.items()}
    data = json.load(open(out)) if os.path.exists(out) else {}
    data['kind'] = 'opacity'; data[key] = rows
    json.dump(data, open(out, 'w'))
    print(f'{key}: opacité mesurée sur {len(rows)} images ({int(mask.sum())} pixels de référence, image {rf}) -> {out}')


if __name__ == '__main__':
    main()
