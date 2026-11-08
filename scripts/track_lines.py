"""Track thin straight lines (grids, guides, frames) on every frame: x of vertical lines, y of horizontal lines.

Usage: python3 track_lines.py <video> <f0> <f1> <out.json> [--bg HEX] [--tol 10] [--min-cover 0.25] [--key lines]
A column (row) is a line when, over at least --min-cover of the frame height (width), its pixels differ from the
background by more than --tol while its neighbours 3 px away do not. Positions are sub-pixel (weighted centre).
Output merged into out.json[key] = {frame: {"v": [x...], "h": [y...]}}. Then, per line, track_fit.py-style
fitting: python3 track_lines.py ... --fit ref.mp4 tracks.json --id grille   (fits each line's position over time,
matching lines frame to frame by nearest position).
"""
import sys, os, json
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mkcommon as mk  # noqa: E402


def peaks(profile, thr):
    out = []
    p = profile
    for i in range(3, len(p) - 3):
        if p[i] >= thr and p[i] >= p[i - 1] and p[i] >= p[i + 1] and p[i - 3] < 0.6 * p[i] and p[i + 3] < 0.6 * p[i]:
            w = p[i - 1:i + 2]; out.append(round(float(i - 1 + (w * np.arange(3)).sum() / max(w.sum(), 1e-9)), 2))
    merged = []
    for x in out:
        if merged and x - merged[-1] < 4:
            continue
        merged.append(x)
    return merged


def main():
    a = sys.argv
    if len(a) < 5:
        sys.exit(__doc__)
    video, f0, f1, out = a[1], int(a[2]), int(a[3]), a[4]
    tol = mk.arg(a, 'tol', 10, float); cover = mk.arg(a, 'min-cover', 0.25, float); key = mk.arg(a, 'key', 'lines')
    cap = cv2.VideoCapture(video); cap.set(cv2.CAP_PROP_POS_FRAMES, f0)
    bg = mk.arg(a, 'bg', None)
    rows = {}
    for f in range(f0, f1 + 1):
        ok, im = cap.read()
        if not ok:
            break
        im = im.astype(np.float32)
        b = np.array([int(bg[i:i + 2], 16) for i in (4, 2, 0)], np.float32) if bg else np.median(im.reshape(-1, 3), axis=0)
        d = (np.abs(im - b).max(axis=2) > tol).astype(np.float32)
        v = peaks(d.mean(axis=0), cover); h = peaks(d.mean(axis=1), cover)
        rows[f] = {'v': v, 'h': h}
    data = json.load(open(out)) if os.path.exists(out) else {}
    data[key] = rows
    json.dump(data, open(out, 'w'))
    nv = [len(r['v']) for r in rows.values()]; nh = [len(r['h']) for r in rows.values()]
    print(f'{key}: {len(rows)} images, lignes verticales {min(nv, default=0)}–{max(nv, default=0)}, horizontales {min(nh, default=0)}–{max(nh, default=0)} -> {out}')
    if '--fit' in a:
        ref, tracks = a[a.index('--fit') + 1], a[a.index('--fit') + 2]
        eid = mk.arg(a, 'id', key)
        from track_fit import fit, moves
        V = mk.probe(ref); fps = V['fps']
        res = json.load(open(tracks)) if os.path.exists(tracks) else {}
        for axis, size in (('v', V['w']), ('h', V['h'])):
            # follow each line from the frame where the most lines are visible, nearest neighbour both ways
            fr = sorted(rows)
            if not fr:
                continue
            ref_f = max(fr, key=lambda k: len(rows[k][axis]))
            for li, x0 in enumerate(rows[ref_f][axis]):
                tr = {ref_f: x0}
                for seq in (fr[fr.index(ref_f) + 1:], fr[:fr.index(ref_f)][::-1]):
                    last = x0
                    for k in seq:
                        c = rows[k][axis]
                        if not c:
                            break
                        n = min(c, key=lambda x: abs(x - last))
                        if abs(n - last) > 25:
                            break
                        tr[k] = n; last = n
                ks = sorted(tr); vals = [tr[k] for k in ks]
                mv = []
                for s0, s1 in moves(np.array(ks), vals, 0.4, 3):
                    t = np.array(ks[s0:s1 + 1]) / fps; y = np.array(vals[s0:s1 + 1])
                    r = fit(t.tolist(), y.tolist(), fps)
                    mv.append({'prop': 'x' if axis == 'v' else 'y', 'ease': r['ease'], 'start': r['start'], 'duration': r['duration'],
                               'from': r['from'], 'to': r['to'], 'from_norm': round(r['from'] / size, 5), 'to_norm': round(r['to'] / size, 5),
                               'rmse_px': r['rmse'], 'source': 'mesuré (track_lines)'})
                lid = f'{eid}_{axis}{li}'
                res[lid] = {'id': lid, 'role': 'ligne', 'ref_size': [V['w'], V['h']], 'fps': fps,
                            'appear': {'frame': ks[0], 't': round(ks[0] / fps, 4)}, 'disappear': {'frame': ks[-1], 't': round(ks[-1] / fps, 4)},
                            'rest': {('cx' if axis == 'v' else 'cy'): {'px': vals[-1], 'norm': round(vals[-1] / size, 5)}}, 'motions': mv}
                print(f"  {lid}: visible {ks[0] / fps:.2f}–{ks[-1] / fps:.2f} s, " + '; '.join(f"{m['ease']} {m['start']}+{m['duration']} s {m['from']:.0f}->{m['to']:.0f}" for m in mv))
        mk.save_json(res, tracks)


if __name__ == '__main__':
    main()
