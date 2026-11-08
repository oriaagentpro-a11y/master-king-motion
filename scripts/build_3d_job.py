"""Build the Blender job of a 3D shot: for every frame of the NEW video, the measured pose of the object (through the
time warp) and the state of its 3D parts (cards...) in real time, anchored on the spoken words.

Usage: python3 build_3d_job.py <spec.json> <out job.json>
spec.json (project file, every value with its source in notes.json):
{ "timing": "timing.json", "scene": "P3", "fps_ref": 30, "fov": 8.5, "pose_file": "analysis/A_baikov/pose3d.json",
  "pose": [ {"from": 318, "to": 329, "extrap": {"src": "A_phone_wide", "fit": [330, 335]}},   (or "hold": {...})
            {"from": 328, "to": 342, "src": "A_phone_wide"},
            {"from": 342, "to": 350, "keys": {"342": {...}, "347": {...}, "350": {...}}, "ease": "power2.in"},
            {"from": 350, "to": 351, "hold_key": {...}},
            {"from": 352, "to": 410, "src": "A_phone_closeup", "clamp": [353, 402]} ],
  "cards": {"w": 0.3637, "h": 0.1528, "items": [{"image": "...card0.png", "y": 0.069}, ...],
            "motions": "A_cards" | [...], "dna": "analysis/motion_dna.json", "stagger": 0.1,
            "words": [[0, 1], [0, 3], [0, 5]], "realtime": true},
  "screen": "assets/render3d/tex/screen.png", "out": "out/render3d/P3/f_####.png", "samples": 64,
  "colors": {...}, "hdri": "...", "motion_blur": 0.5 }
Pose segments are in REFERENCE frames (fractional frames interpolate linearly). Cards: each card starts at
max(first measured start + i * stagger, the spoken word), converted to new time; its measured moves then play in REAL
time (rule 11: a gesture is never slowed by the stretch of a hold).
"""
import sys, os, json, math
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fit_easing import ease  # noqa: E402

KEYS = ('x', 'y', 'z', 'rx', 'ry', 'rz')


def lerp_knots(k, x, a, b):
    if x <= k[0][a]:
        return k[0][b] + (x - k[0][a])
    for i in range(1, len(k)):
        if x <= k[i][a]:
            p, q = k[i - 1], k[i]; sp = q[a] - p[a]
            return q[b] if sp <= 1e-9 else p[b] + (x - p[a]) * (q[b] - p[b]) / sp
    return k[-1][b] + (x - k[-1][a])


def gsap_ease(name):
    n = name.split('(')[0]
    try:
        return ease(n)
    except Exception:
        return lambda p: p


def main():
    spec_p, out = sys.argv[1], sys.argv[2]
    S = json.load(open(spec_p)); base = os.path.dirname(os.path.abspath(spec_p))
    P = lambda p: p if os.path.isabs(p) else os.path.join(base, p)
    T = json.load(open(P(S['timing']))); sc = next(s for s in T['scenes'] if s['id'] == S['scene'])
    fps = T['stage']['fps']; fr_ref = S.get('fps_ref', 30)
    poses = json.load(open(P(S['pose_file'])))
    # a reference converted 25 -> 30 i/s repeats one frame in six: its tracked poses stall there. Resample every track
    # on the DISTINCT frames, on the true clock (rule 52), or the 3D object stutters exactly like the conversion.
    import mkcommon as mk
    pd = mk.pulldown(sc['source']) if sc.get('source') and S.get('pulldown', True) else None
    if pd:
        print(f"référence à images dupliquées 1/{pd['period']} : poses rééchantillonnées sur {pd['true_fps']:.3g} i/s")

    def track(src, f):
        if pd:
            D = pd['distinct']; jx = (f / fr_ref - pd['offset']) * pd['true_fps']
            j0 = int(np.clip(np.floor(jx), 0, len(D) - 1)); j1 = min(len(D) - 1, j0 + 1); u = float(np.clip(jx - j0, 0, 1))
            A, B = track_raw(src, D[j0]), track_raw(src, D[j1])
            return {k: A[k] + (B[k] - A[k]) * u for k in KEYS}
        return track_raw(src, f)

    def track_raw(src, f):
        fr = poses[src]['frames']; ks = sorted(int(k) for k in fr)
        f = min(max(f, ks[0]), ks[-1]); lo = max(k for k in ks if k <= f); hi = min(k for k in ks if k >= f)
        A, B = fr[str(lo)], fr[str(hi)]; t = 0 if hi == lo else (f - lo) / (hi - lo)
        return {k: A[k] + (B[k] - A[k]) * t for k in KEYS}

    def pose_at(f):
        for seg in S['pose']:
            if seg['from'] <= f <= seg['to'] + 0.999:
                if 'hold' in seg:
                    return track(seg['hold']['src'], seg['hold']['frame'])
                if 'extrap' in seg:
                    # before the first reliable tracked frame: continue the MEASURED motion (linear fit over a clean
                    # window) instead of freezing it: a held pose is a dead frame the reference does not have (rule 66)
                    e_ = seg['extrap']; fr_ = poses[e_['src']]['frames']
                    ks_ = [k for k in sorted(int(k) for k in fr_) if e_['fit'][0] <= k <= e_['fit'][1]]
                    return {kk: float(np.polyval(np.polyfit(ks_, [fr_[str(k)][kk] for k in ks_], 1), f)) for kk in KEYS}
                if 'hold_key' in seg:
                    return dict(seg['hold_key'])
                if 'src' in seg:
                    c = seg.get('clamp')
                    v = track(seg['src'], min(max(f, c[0]), c[1]) if c else f)
                    for k, d in seg.get('add', {}).items():   # angle continuity after a full turn (rule 40: never wrap)
                        v[k] += d
                    sd = seg.get('screen_dx')
                    if sd and c and f > c[1]:
                        # measured on-screen slide past the last reliable pose (blur breaks the tracking): fitted tween
                        # in reference px (sd['px_h'] = reference height), converted to X at the object's depth
                        def px(t):
                            q = float(np.clip((t - sd['start']) / sd['duration'], 0, 1)); return sd['from'] + (sd['to'] - sd['from']) * float(gsap_ease(sd['ease'])(q))
                        d_px = px(f / fr_ref) - px(c[1] / fr_ref)
                        v['x'] += d_px * 2 * abs(v['z']) * math.tan(math.radians(S['fov'] / 2)) / sd['px_h']
                    return v
                if 'keys' in seg:
                    ks = sorted((int(k), v) for k, v in seg['keys'].items()); e = gsap_ease(seg.get('ease', 'none'))
                    f0, f1 = ks[0][0], ks[-1][0]; g = f0 + (f1 - f0) * float(e(np.clip((f - f0) / (f1 - f0), 0, 1)))
                    for (a_, A), (b_, B) in zip(ks, ks[1:]):
                        if a_ <= g <= b_:
                            t = (g - a_) / (b_ - a_); return {k: A[k] + (B[k] - A[k]) * t for k in KEYS}
                    return dict(ks[-1][1])
        raise SystemExit(f'image de référence {f:.2f} hors des segments de pose')

    knots = sc['knots']
    C = S.get('cards'); cards_t = []
    if C:
        mv = C['motions']
        if isinstance(mv, str):
            mv = json.load(open(P(C['dna'])))['elements'][mv]['motions']
        mv = sorted(mv, key=lambda m: m['start']); first = mv[0]['start']
        lt0 = first - sc['ref_start']
        for i, it in enumerate(C['items']):
            a = lt0 + i * C.get('stagger', 0.1)
            if i < len(C.get('words', [])):
                k_, j_ = C['words'][i]
                try:
                    w = sc['vo'][k_]['words'][j_]; a = max(a, lerp_knots(knots, w['start'] - sc['new_start'], 1, 0))
                except (IndexError, KeyError):
                    pass
            if cards_t:
                a = max(a, cards_t[-1] + C.get('stagger', 0.1))
            cards_t.append(a)
        starts_new = [lerp_knots(knots, a, 0, 1) for a in cards_t]
    frames = []
    for k in range(sc['new_start_frame'], sc['new_end_frame']):
        tn = k / fps - sc['new_start']
        tr = lerp_knots(knots, tn, 1, 0); f_ref = (sc['ref_start'] + tr) * fr_ref
        item = {'f': k - sc['new_start_frame'] + 1, 'tn': round(tn, 4), 'ref_frame': round(f_ref, 3),
                'pose': {kk: round(v, 6) for kk, v in pose_at(f_ref).items()}}
        if C:
            cs = []
            for i in range(len(C['items'])):
                st = {'z': 0.0, 'rx': 0.0}
                for m in mv:
                    t0 = (starts_new[i] if C.get('realtime', True) else lerp_knots(knots, cards_t[i], 0, 1)) + (m['start'] - first)
                    p = np.clip((tn - t0) / m['duration'], 0, 1)
                    if tn >= t0 or m is mv[0]:
                        prop = 'rx' if m['prop'] in ('rotationX', 'rx') else m['prop']
                        if tn >= t0:
                            st[prop] = m['from'] + (m['to'] - m['from']) * float(gsap_ease(m['ease'])(p))
                # NEVER wrap angles (356 -> 0 would be interpolated backwards over 356 deg inside the motion-blur shutter)
                cs.append({'z': round(st['z'], 5), 'rx': round(st['rx'], 3)})
            item['cards'] = cs
        frames.append(item)
    job = {'W': T['stage']['w'], 'H': T['stage']['h'], 'fps': fps, 'fov': S['fov'], 'out': P(S['out']),
           'samples': S.get('samples', 64), 'motion_blur': S.get('motion_blur', 0.5), 'hdri': P(S['hdri']),
           'hdri_strength': S.get('hdri_strength', 1.0), 'hdri_rot': S.get('hdri_rot', 0), 'colors': S.get('colors', {}),
           'screen': {'image': P(S['screen'])}, 'frames': frames,
           'cards': [{'image': P(it['image']), 'w': C['w'], 'h': C['h'], 'y': it['y']} for it in C['items']] if C else []}
    if S.get('lights') is not None:
        job['lights'] = S['lights']
    json.dump(job, open(out, 'w'), indent=1)
    print(f"job 3D {S['scene']} : {len(frames)} images (réf. f{frames[0]['ref_frame']:.1f} → f{frames[-1]['ref_frame']:.1f}), "
          f"cartes à {[round(x, 3) for x in (starts_new if C else [])]} s (temps nouveau local) -> {out}")


if __name__ == '__main__':
    main()
