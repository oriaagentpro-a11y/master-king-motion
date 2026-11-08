"""Turn a measured track into DNA motion entries: every move of every property, fitted as a GSAP tween.

Usage: python3 track_fit.py <track.json> <ref.mp4> <out.json> --id title --role titre
                            [--key KEY] [--source elements|textbox|template|quad|opacity] [--props cx,cy,w,h,angle,scale,opacity]
                            [--eps 0.6] [--min-move 3] [--pick largest|nearest:x,y] [--curve [--curve-ref last]]
Reads the output of track_elements.py (union box), track_textbox.py (--key), track_template.py or
track_quad.py. For each property the curve is cut into moves (runs where it changes faster than --eps px per
frame, padded by 2 frames) and each move is fitted with fit_easing (ease, start, duration, from, to, rmse).
Values are written in reference pixels AND normalised (x / width, y / height): the new video uses the
normalised values on its own stage (1920x1080 by default), so the composition is kept whatever the size.
--pick (track_elements only): follow one component instead of the union box of everything detected —
'largest', or 'nearest:x,y' (starts at x,y and then follows the closest component frame after frame).
Also written: first / last visible frame (appearance, disappearance) and the overshoot of each move.
The result is merged into out.json under the element id (one file can hold every element of the video).
"""
import sys, os, json
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mkcommon as mk  # noqa: E402
from fit_easing import ease as ease_fn, EASES  # noqa: E402


def fit(times, values, fps):
    """Best GSAP tween for one move. Start searched from 3 frames before to 6 after the detected start (padding), duration from the
    detected length minus 8 frames to 3x (long ease tails sit under the motion threshold); from/to solved in closed form."""
    t = np.asarray(times, float); v = np.asarray(values, float); st = 1 / fps
    L = t[-1] - t[0]; best = None
    starts = t[0] + np.arange(-3, 7) * st
    durs = np.arange(max(2 * st, L - 8 * st), max(3 * st, 3 * L) + st / 2, st)
    for name in EASES:
        e = ease_fn(name)
        for s in starts:
            P = np.clip((t[None, :] - s) / durs[:, None], 0, 1)
            Y = e(P)
            # least squares for v = a(1-y) + b y  ->  v = a + (b-a) y
            ym = Y.mean(1, keepdims=True); vm = v.mean()
            cov = ((Y - ym) * (v - vm)).sum(1); var = ((Y - ym) ** 2).sum(1) + 1e-12
            k = cov / var; a0 = vm - k * ym[:, 0]
            err = np.sqrt((((a0[:, None] + k[:, None] * Y) - v) ** 2).mean(1))
            i = int(np.argmin(err))
            if best is None or err[i] < best['rmse'] - 1e-9:
                best = {'ease': name, 'start': round(float(s), 4), 'duration': round(float(durs[i]), 4),
                        'from': round(float(a0[i]), 3), 'to': round(float(a0[i] + k[i]), 3), 'rmse': round(float(err[i]), 4)}
    return best


def pieces(f, v):
    """Split a curve at visibility gaps and at one-frame jumps (a text replaced by another, a cut)."""
    d = np.abs(np.diff(v)); nz = d[d > 1e-9]
    thr = max(6 * (np.median(nz) if len(nz) else 0), 0.08 * (np.abs(v).max() or 1))
    cut = [0]
    for i in range(len(d)):
        nb = max(d[i - 1] if i > 0 else 0, d[i + 1] if i + 1 < len(d) else 0)
        if f[i + 1] - f[i] > 1 or (d[i] > thr and nb < 0.4 * d[i]):
            cut.append(i + 1)
    cut.append(len(v))
    return [(cut[k], cut[k + 1]) for k in range(len(cut) - 1) if cut[k + 1] - cut[k] >= 4]


def load(path, source, key, pick=None):
    J = json.load(open(path))
    rows = {}
    if source == 'opacity' or (source is None and J.get('kind') == 'opacity'):
        for f, o in J[key or 'opacity'].items():
            rows[int(f)] = {'opacity': o}
        return dict(sorted(rows.items()))
    if source == 'textbox' or (source is None and key and key in J):
        for f, b in J[key].items():
            x, y, w, h = b; rows[int(f)] = {'cx': x + w / 2, 'cy': y + h / 2, 'w': w, 'h': h, 'left': x, 'top': y}
    elif source == 'template' or (source is None and 'template' in J):
        tw, th = J['template'][2], J['template'][3]
        for r in J['rows']:
            if r.get('x') is None:
                continue
            s = r['scale']; rows[r['frame']] = {'cx': r['x'] + tw * s / 2, 'cy': r['y'] + th * s / 2, 'scale': s, 'w': tw * s, 'h': th * s}
    elif source == 'quad' or (source is None and isinstance(J.get('rows'), dict)):
        for f, r in J['rows'].items():
            rows[int(f)] = {'cx': r['center'][0], 'cy': r['center'][1], 'angle': r['angle'], 'w': r['size'][0], 'h': r['size'][1],
                            'left': min(q[0] for q in r['quad']), 'top': min(q[1] for q in r['quad']),
                            'right': max(q[0] for q in r['quad']), 'bottom': max(q[1] for q in r['quad'])}
    else:  # track_elements: union box, or one component followed frame to frame (--pick)
        prev = None
        if pick and pick.startswith('nearest:'):
            prev = tuple(map(float, pick.split(':')[1].split(',')))
        for r in J['rows']:
            u = r.get('union')
            if pick and r.get('components'):
                cs = r['components']
                if pick == 'largest':
                    c = max(cs, key=lambda c: c['area'])
                else:
                    c = min(cs, key=lambda c: np.hypot(c['cx'] - prev[0], c['cy'] - prev[1]))
                prev = (c['cx'], c['cy'])
                u = {'x': c['x'], 'y': c['y'], 'w': c['w'], 'h': c['h']}
            if u:
                rows[r['frame']] = {'cx': u['x'] + u['w'] / 2, 'cy': u['y'] + u['h'] / 2, 'w': u['w'], 'h': u['h'], 'left': u['x'], 'top': u['y']}
    return dict(sorted(rows.items()))


def moves(frames, vals, eps, min_move):
    v = np.asarray(vals, float)
    if len(v) < 4:
        return []
    sm = np.convolve(v, np.ones(3) / 3, mode='same'); sm[0], sm[-1] = v[0], v[-1]
    vel = np.abs(np.gradient(sm))
    act = vel > eps
    out, s = [], None
    for i, a in enumerate(list(act) + [False]):
        if a and s is None:
            s = i
        if not a and s is not None:
            a0, a1 = max(0, s - 2), min(len(v) - 1, i + 1)
            if abs(v[a1] - v[a0]) >= min_move or np.ptp(v[a0:a1 + 1]) >= min_move:
                out.append((a0, a1))
            s = None
    merged = []
    for m in out:  # merge moves separated by 1-2 still frames (one movement with a slow middle)
        if merged and m[0] - merged[-1][1] <= 2:
            merged[-1] = (merged[-1][0], m[1])
        else:
            merged.append(m)
    return merged


def main():
    a = sys.argv
    if len(a) < 4:
        sys.exit(__doc__)
    track, ref, out = a[1], a[2], a[3]
    eid = mk.arg(a, 'id', 'element'); role = mk.arg(a, 'role', None); key = mk.arg(a, 'key', None)
    source = mk.arg(a, 'source', None); eps = mk.arg(a, 'eps', 0.6, float); min_move = mk.arg(a, 'min-move', 3, float)
    V = mk.probe(ref); fps, W, H = V['fps'], V['w'], V['h']
    rows = load(track, source, key, mk.arg(a, 'pick', None))
    if not rows:
        sys.exit('piste vide : rien à ajuster')
    # a box touching the frame edge is cut by the frame: its size / centre are wrong there -> not used
    for f, r in rows.items():
        if 'left' in r:
            right = r.get('right', r['left'] + r.get('w', 0)); bottom = r.get('bottom', r['top'] + r.get('h', 0))
            r['clipped'] = r['left'] <= 1 or r['top'] <= 1 or right >= W - 2 or bottom >= H - 2
    frames = np.array(list(rows))
    props = (mk.arg(a, 'props', None) or ','.join(k for k in ['cx', 'cy', 'w', 'h', 'angle', 'scale'] if k in rows[frames[0]])).split(',')
    norm = {'cx': W, 'left': W, 'w': W, 'cy': H, 'top': H, 'h': H}
    res = {'id': eid, 'role': role, 'ref_size': [W, H], 'fps': fps, 'source_track': os.path.basename(track),
           'appear': {'frame': int(frames[0]), 't': round(frames[0] / fps, 4)},
           'disappear': {'frame': int(frames[-1]), 't': round(frames[-1] / fps, 4)},
           'rest': {}, 'motions': []}
    gaps = np.where(np.diff(frames) > 1)[0]
    if len(gaps):
        res['visibility_gaps'] = [[int(frames[g]), int(frames[g + 1])] for g in gaps]
    clipped = [int(x) for x in frames if rows[x].get('clipped')]
    if clipped:
        res['clipped_frames'] = [clipped[0], clipped[-1], len(clipped)]
    allm = []
    for p in props:
        geo = p in ('cx', 'cy', 'w', 'h', 'left', 'top')
        f = np.array([x for x in frames if not (geo and rows[x].get('clipped'))])
        if len(f) < 2:
            continue
        v = np.array([rows[x][p] for x in f], float)
        if p == 'angle':  # minAreaRect / corner order wraps: unwrap with the shape's symmetry period
            ww = np.median([rows[x]['w'] for x in f]); hh = np.median([rows[x]['h'] for x in f])
            per = 90.0 if abs(ww - hh) / max(ww, hh, 1e-6) < 0.12 else 180.0
            v = np.degrees(np.unwrap(np.radians(v) * (360 / per)) * (per / 360))
        if p == 'opacity':
            eps_p, mm = max(0.01, eps / 60), max(0.05, min_move / 60)
        else:
            eps_p, mm = eps, min_move
        last = v[-1]; res['rest'][p] = {'px': round(float(last), 3), **({'norm': round(float(last) / norm[p], 5)} if p in norm else {})}
        for b0, b1 in pieces(f, v):
          for a0, a1 in moves(f[b0:b1], v[b0:b1], eps_p, mm):
            a0 += b0; a1 += b0
            t = f[a0:a1 + 1] / fps; y = v[a0:a1 + 1]
            r = fit(t.tolist(), y.tolist(), fps)
            if r is None:
                continue
            span = r['to'] - r['from']
            over = float(np.max((y - r['to']) * np.sign(span))) if span else 0.0
            m = {'prop': p, 'ease': r['ease'], 'start': r['start'], 'duration': r['duration'],
                 'start_frame': int(round(r['start'] * fps)), 'from': r['from'], 'to': r['to'], 'rmse_px': r['rmse'],
                 'overshoot_px': round(max(0.0, over), 2)}
            if p in norm:
                m['from_norm'] = round(r['from'] / norm[p], 5); m['to_norm'] = round(r['to'] / norm[p], 5)
            m['speed_peak_px_s'] = round(float(np.max(np.abs(np.gradient(y))) * fps), 1)
            tol = max(0.02, 0.03 * abs(span)) if p == 'opacity' else max(1.0, 0.03 * abs(span))
            m['quality'] = 'ok' if r['rmse'] <= tol else 'à décalquer (trackAt) : une seule courbe ne suffit pas'
            nxt = int(f[a1]) + 1
            if geo and nxt in rows and rows[nxt].get('clipped'):
                m['truncated'] = True
                m['quality'] = ('coupé par le bord du cadre : durée et valeur finale EXTRAPOLÉES — confirmer la fin à l\'œil '
                                '(ex. image où l\'écran est plein) et corriger duration / to dans notes.json')
            res['motions'].append(m)
    # --curve: the measured curve itself, normalised, frame by frame (décalque): cx, cy / frame size and s = scale
    # relative to the reference frame (--curve-ref first|last|max|F; from the mask area when known: robust to rotation)
    if '--curve' in a:
        J = json.load(open(track)); ar = J.get((key or '') + '_area', {})
        fr_ok = [int(x) for x in frames if not rows[x].get('clipped')]
        cref = mk.arg(a, 'curve-ref', 'last')
        if cref == 'first':
            rf = fr_ok[0]
        elif cref == 'last':
            rf = fr_ok[-1]
        elif cref == 'max':
            rf = max(fr_ok, key=lambda x: float(ar.get(str(x), 0)) or rows[x].get('h', 0))
        else:
            rf = int(cref)
        a_ref = float(ar.get(str(rf), 0)); h_ref = rows[rf].get('h') or 1
        cur = {}
        for x in frames:
            r = rows[x]; c = {}
            if not r.get('clipped'):
                if 'cx' in r: c['cx'] = round(r['cx'] / W, 5)
                if 'cy' in r: c['cy'] = round(r['cy'] / H, 5)
            if a_ref and str(x) in ar:
                c['s'] = round(float(np.sqrt(float(ar[str(x)]) / a_ref)), 4)
            elif 'h' in r and not r.get('clipped'):
                c['s'] = round(r['h'] / h_ref, 4)
            if 'angle' in r: c['angle'] = round(r['angle'], 3)
            if 'opacity' in r: c['opacity'] = r['opacity']
            if c:
                cur[int(x)] = c
        res['curve'] = {'fps': fps, 'ref_frame': rf, 'frames': cur,
                        'note': 'décalque : rejouer avec MK.curveAt(curve, t_ref_absolu) dans frame(tn, tr) (tr + ctx.refStart)'}
    res['motions'].sort(key=lambda m: (m['start'], m['prop']))
    # repeated motif (one pop per beat, a stagger...): summarise it, it is often what must be reproduced
    from collections import Counter
    for p in props:
        ms = [m for m in res['motions'] if m['prop'] == p]
        if len(ms) >= 3:
            st = np.array([m['start'] for m in ms]); iv = np.diff(st)
            if len(iv) and np.std(iv) < 0.25 * np.mean(iv):
                good = [m for m in ms if m['quality'] == 'ok'] or ms
                res.setdefault('patterns', []).append({
                    'prop': p, 'count': len(ms), 'every_s': round(float(np.median(iv)), 4), 'first': ms[0]['start'],
                    'ease': Counter(m['ease'] for m in good).most_common(1)[0][0],
                    'duration_s': round(float(np.median([m['duration'] for m in good])), 4),
                    'amplitude_ratio': round(float(np.median([m['from'] / m['to'] for m in good if m['to']])), 3),
                    'note': 'motif répété : à rejouer tel quel (même intervalle, même ease) ; caler l\'intervalle sur le tempo de la nouvelle musique si la référence le calait sur le sien'})
    data = json.load(open(out)) if os.path.exists(out) else {}
    data[eid] = res
    mk.save_json(data, out)
    for m in res['motions']:
        print(f"  {eid}.{m['prop']:5s} {m['ease']:13s} départ {m['start']:8.4f} s  durée {m['duration']:6.4f} s  "
              f"{m['from']:8.2f} -> {m['to']:8.2f}  (rmse {m['rmse_px']} px)  {m['quality']}")
    for pt in res.get('patterns', []):
        print(f"  motif {eid}.{pt['prop']}: {pt['count']} fois, toutes les {pt['every_s']} s, {pt['ease']} {pt['duration_s']} s, "
              f"départ à {pt['amplitude_ratio']} de la taille finale")
    print(f"{eid}: {len(res['motions'])} mouvements, visible {res['appear']['t']}–{res['disappear']['t']} s -> {out}")


if __name__ == '__main__':
    main()
