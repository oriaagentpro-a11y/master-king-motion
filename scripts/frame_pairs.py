"""Frame-by-frame review sheet: REFERENCE | NEW at the same instants (the core of the verification pass).

Usage: python3 frame_pairs.py timing.json new.mp4 out.png f1 f2 ... [--ref-replay out/compare/reference_recalee.mp4]
                              [--raw] [--crop x0,y0,x1,y1] [--stills dir] [--width 480]
- default: left = the reference REPLAYED on the new clock (style_compare.py writes it), right = new.mp4, same frame.
- --raw: left = the SOURCE frame of the reference scene mapped through the warp (scene 'source', knots, rhythm),
  no blending (use it to tell a real effect from a replay blend, and to read duplicated frames: rule 52).
- --crop x0,y0,x1,y1 (pixels of the NEW video, e.g. 1920x1080): pixel zoom on the same region of both sides
  (the reference is upscaled to the new size first): phone bezel, camera island, text edges, icon detail (rule 57).
- --stills dir: take the new frame from dir/fNNNNN.png (render_film.py --stills) instead of new.mp4.
Each row is labelled with the new frame, the reference frame and the scene id.
"""
import os as _o, sys as _s; _s.path.insert(0, _o.path.dirname(_o.path.abspath(__file__))); import _mkpy  # noqa: E401,E702,F401  (bon Python + PATH)
import sys, os, json
import cv2
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mkcommon as mk  # noqa: E402
from style_compare import scene_to_ref  # noqa: E402


def grab(path, f):
    c = cv2.VideoCapture(path); c.set(cv2.CAP_PROP_POS_FRAMES, int(f)); ok, im = c.read(); c.release()
    if not ok:
        raise SystemExit(f'image {f} illisible dans {path}')
    return im


def main():
    a = sys.argv
    if len(a) < 5:
        sys.exit(__doc__)
    T = json.load(open(a[1])); new, out = a[2], a[3]
    frames, i = [], 4
    while i < len(a):
        if a[i].startswith('--'):
            i += 1 if a[i] == '--raw' else 2; continue
        frames.append(int(a[i])); i += 1
    rw = mk.arg(a, 'width', 480, int); raw = '--raw' in a; crop = mk.arg(a, 'crop'); stills = mk.arg(a, 'stills')
    replay = mk.arg(a, 'ref-replay', 'out/compare/reference_recalee.mp4')
    W, H, fps = T['stage']['w'], T['stage']['h'], T['stage']['fps']
    rows = []
    for f in frames:
        s = next((x for x in T['scenes'] if x['new_start_frame'] <= f < x['new_end_frame']), T['scenes'][-1])
        tr = scene_to_ref(s, f / fps - s['new_start']); src = s.get('source')
        rf = (s['ref_start'] + tr) * mk.probe(src)['fps'] if src else None
        if raw:
            ri = grab(src, round(rf))
        else:
            ri = grab(replay, f)
        ni = cv2.imread(os.path.join(stills, f'f{f:05d}.png')) if stills else grab(new, f)
        ri = cv2.resize(ri, (W, H), interpolation=cv2.INTER_CUBIC); ni = cv2.resize(ni, (W, H), interpolation=cv2.INTER_AREA)
        if crop:
            x0, y0, x1, y1 = [int(v) for v in crop.split(',')]; ri, ni = ri[y0:y1, x0:x1], ni[y0:y1, x0:x1]
        h_ = int(rw * ri.shape[0] / ri.shape[1])
        A = Image.fromarray(cv2.cvtColor(ri, cv2.COLOR_BGR2RGB)).resize((rw, h_)); B = Image.fromarray(cv2.cvtColor(ni, cv2.COLOR_BGR2RGB)).resize((rw, h_))
        r = Image.new('RGB', (2 * rw + 10, h_ + 20), (20, 20, 24)); r.paste(A, (0, 20)); r.paste(B, (rw + 10, 20))
        ImageDraw.Draw(r).text((4, 3), f"{s['id']} nouveau f{f} | réf. {s.get('ref')} f{rf:.1f}" + (' (brute)' if raw else ' (rejouée)'), fill=(255, 220, 120))
        rows.append(r)
    S = Image.new('RGB', (rows[0].width, sum(r.height for r in rows)))
    y = 0
    for r in rows:
        S.paste(r, (0, y)); y += r.height
    S.save(out); print(f'{len(rows)} paires -> {out}')


if __name__ == '__main__':
    main()
