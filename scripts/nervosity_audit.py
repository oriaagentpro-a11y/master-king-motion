"""Nervousness audit: is the new video as NERVOUS as the reference? Scene by scene, with numbers (rule 74).

Usage: python3 nervosity_audit.py timing.json out/compare/reference_recalee.mp4 out/film_silent.mp4
                                  [--audio analysis/audio_plan.json] [--dead 0.3] [--json out.json]
For each scene:
  étirements  the warp sections whose speed is not 1 (new / reference duration): gestures placed there are SLOWED
              unless the recipe plays them in real time on tn (rule 59) — list them and check each gesture inside.
  énergie     mean motion energy new / replayed reference, overall and in the stretched sections only.
  vitesse     95th percentile of the energy (the fastest moments): new / reference. Below 0.8 = less punchy.
  zones mortes  windows >= --dead s where our energy is < 25 % of the reference's while the reference moves.
              Confirm each with pixel differences (an energy hole can be an artefact on thin lines, rule 67).
  coupes      distance of each scene start (cut) to the nearest music beat (beats converted to video time with
              music_start / music_offset): > 2 frames = off the beat.
Read the list, then fix: gestures in real time, continuous motion instead of holds, cuts on beats.
"""
import sys, os, json
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mkcommon as mk  # noqa: E402


def main():
    a = sys.argv
    if len(a) < 4:
        sys.exit(__doc__)
    T = json.load(open(a[1])); fps = T['stage']['fps']
    R = np.array(mk.curves(a[2])['energy']); N = np.array(mk.curves(a[3])['energy']); n = min(len(R), len(N))
    dead = mk.arg(a, 'dead', 0.3, float); out = {'scenes': []}
    beats = []
    ap = mk.arg(a, 'audio', 'analysis/audio_plan.json')
    if os.path.exists(ap):
        A = json.load(open(ap)); ms = T.get('music_start', 0.0) or 0.0; mo = T.get('music_offset', 0.0) or 0.0
        beats = [b['t'] - ms + mo for b in A['music']['beats'] if 0 <= b['t'] - ms + mo <= T['total']]
    print(f"{'scène':6s} {'étirements (vitesse)':34s} {'énergie':>8s} {'dans étirés':>11s} {'vitesse p95':>11s}  coupe/temps")
    for s in T['scenes']:
        f0, f1 = s['new_start_frame'], min(s['new_end_frame'], n)
        k = s['knots']; secs = []
        for (r0, n0), (r1, n1) in zip(k, k[1:]):       # knots = [reference local, new local]
            if r1 - r0 > 1e-3 and n1 - n0 > 1e-3 and abs((n1 - n0) / (r1 - r0) - 1) > 0.05:
                secs.append((s['new_start'] + n0, s['new_start'] + n1, (n1 - n0) / (r1 - r0)))   # new / ref = stretch
        r, m = R[f0 + 1:f1], N[f0 + 1:f1]
        e_all = float(m.mean() / (r.mean() + 1e-9)) if len(r) else 1.0
        idx = [i for i in range(f0 + 1, f1) if any(x0 * fps <= i < x1 * fps for x0, x1, _ in secs)]
        e_str = float(N[idx].mean() / (R[idx].mean() + 1e-9)) if idx else None
        p95 = float(np.percentile(m, 95) / (np.percentile(r, 95) + 1e-9)) if len(r) else 1.0
        # dead zones
        w = max(2, int(round(dead * fps))); zones = []; i = f0 + 1
        while i + w <= f1:
            rr, nn = R[i:i + w], N[i:i + w]
            if rr.mean() > 0.15 * R[f0:f1].max() and nn.mean() < 0.25 * rr.mean():
                j = i + w
                while j < f1 and N[j] < 0.25 * R[j] and R[j] > 0:
                    j += 1
                zones.append((i, j - 1)); i = j
            else:
                i += 1
        cut = s['new_start']; bd = min((abs(cut - b) for b in beats), default=None)
        st = ', '.join(f"{x0:.2f}-{x1:.2f}s étiré x{v:.2f}" for x0, x1, v in secs) or '—'
        print(f"{s['id']:6s} {st:34s} {e_all:8.2f} {('%.2f' % e_str) if e_str is not None else '—':>11s} {p95:11.2f}  "
              + (f"{bd * fps:.1f} img" if bd is not None else '—'))
        for z0, z1 in zones:
            print(f"       zone morte images {z0}-{z1} ({z0 / fps:.2f}-{z1 / fps:.2f} s)")
        out['scenes'].append({'id': s['id'], 'stretches': secs, 'energy': e_all, 'energy_stretched': e_str, 'p95': p95,
                              'dead_zones': zones, 'cut_to_beat_frames': None if bd is None else bd * fps})
    if mk.arg(a, 'json'):
        json.dump(out, open(mk.arg(a, 'json'), 'w'), indent=1)


if __name__ == '__main__':
    main()
