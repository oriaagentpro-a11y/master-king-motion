"""Measure how WORDS arrive and leave in a reference: per frame, every word's ink box, its contrast (opacity) and
its colour saturation (accent / flash), on the reference's DISTINCT frames (rule 52).

Usage: python3 word_ink.py ref.mp4 f0 f1 --band y0,y1 [--x x0,x1] [--gap 9] [--dark 25] [--json out.json]
- --band: the text rows (reference pixels). Grid lines crossing the band show as tall boxes: ignore boxes taller
  than the text (or narrow the band).
- words = column groups separated by more than --gap pixels of background.
Read: a new word that appears LOWER (y0 larger) and PALE (low contrast) then reaches its row = rise + fade-in
(measure the offset in px / ref height and the number of distinct frames = duration); a word whose saturation jumps
(sat 40+ against ~15) is the accent colour; a word whose letters change shape frame to frame = scramble.
Then fit the series with fit_easing.py and write the values with their source in notes.json.
"""
import sys, os, json
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mkcommon as mk  # noqa: E402


def main():
    a = sys.argv
    if len(a) < 4:
        sys.exit(__doc__)
    ref, f0, f1 = a[1], int(a[2]), int(a[3])
    y0, y1 = [int(v) for v in mk.arg(a, 'band').split(',')]
    R = mk.probe(ref); x0, x1 = [int(v) for v in (mk.arg(a, 'x') or f'0,{R["w"]}').split(',')]
    gap = mk.arg(a, 'gap', 9, int); dark = mk.arg(a, 'dark', 25, int)
    pd = mk.pulldown(ref); D = set(pd['distinct']) if pd else None
    c = cv2.VideoCapture(ref); res = {}
    for f in range(f0, f1 + 1):
        c.set(cv2.CAP_PROP_POS_FRAMES, f); ok, im = c.read()
        if not ok:
            break
        im = im.astype(float); g = im.mean(2); sat = im.max(2) - im.min(2)
        band = g[y0:y1, x0:x1]; sb = sat[y0:y1, x0:x1]; bg = np.median(band); m = band < bg - dark
        cols = np.where(m.sum(0) >= 2)[0]; words = []
        if len(cols):
            for grp in np.split(cols, np.where(np.diff(cols) > gap)[0] + 1):
                if len(grp) < 4:
                    continue
                sub = m[:, grp[0]:grp[-1] + 1]; rows = np.where(sub.sum(1) > 0)[0]
                words.append({'x': [int(grp[0] + x0), int(grp[-1] + x0)], 'y': [int(rows.min() + y0), int(rows.max() + y0)],
                              'contrast': int(bg - band[:, grp[0]:grp[-1] + 1][sub].mean()), 'sat': int(sb[:, grp[0]:grp[-1] + 1][sub].mean())})
        tag = 'dup' if D is not None and f not in D else '   '
        res[f] = {'dup': tag == 'dup', 'words': words}
        print(f, tag, ' | '.join(f"x{w['x'][0]}-{w['x'][1]} y{w['y'][0]}-{w['y'][1]} c{w['contrast']} s{w['sat']}" for w in words))
    if mk.arg(a, 'json'):
        json.dump(res, open(mk.arg(a, 'json'), 'w'), indent=1)


if __name__ == '__main__':
    main()
