"""Time the new video: each plan scene gets the length its voice-over needs, cuts land on the user's music,
and every measured animation keeps its exact speed (only the hold between entrance and exit stretches).

Usage: python3 retime.py <plan.json> <out timing.json> [--audio audio_plan.json]
plan.json (written by Claude in phase 2, validated by the user with the storyboard):
{ "stage": {"w": 1920, "h": 1080, "fps": 30},
  "dna": "analysis/motion_dna.json",
  "snap": "beats" | "downbeats" | "none",        // default: beats when the reference cuts on the beat
  "voice_offset": 0.6,                            // s: where the voice-over starts in the new video
  "lead": 0.15, "pad_after": 0.35, "min_hold": 0.4, "tail": 1.2,
  "scenes": [ {"id": "P01", "ref": "S01", "vo": [0, 1], "slots": {...}},
              {"id": "P02", "ref": "S02", "vo": [2], "items": 5},   // rhythmic scene: 5 words, one per beat
              {"id": "P03", "ref": "S02", "vo": [3], "note": "S02 reused for a 2nd feature"},
              {"id": "P04", "ref": "S04", "duration": 3.0} ] }
A plan scene may reuse a reference scene (more content than the reference) or skip one.
Writes timing.json and timing.js (window.TIMING, read by mkm.js) with, per plan scene: new start / end,
the warp knots [[t_ref_local, t_new_local], ...] (identity on the entrance, shift on the exit; a longer hold is
stretched linearly, a shorter hold is played at speed 1 and its end skipped — a hold is never sped up), its voice-over phrases, and warnings (voice too dense for the animations, music too short...).
"""
import os as _o, sys as _s; _s.path.insert(0, _o.path.dirname(_o.path.abspath(__file__))); import _mkpy  # noqa: E401,E702,F401  (bon Python + PATH)
import sys, os, json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mkcommon as mk  # noqa: E402


def main():
    a = sys.argv
    if len(a) < 3:
        sys.exit(__doc__)
    P = json.load(open(a[1])); out = a[2]
    base = os.path.dirname(os.path.abspath(a[1]))
    dna = json.load(open(os.path.join(base, P['dna'])))
    ap = mk.arg(a, 'audio', None)
    A = json.load(open(ap)) if ap else {}
    ref = {s['id']: s for s in dna['scenes']}
    stage = P.get('stage', {'w': 1920, 'h': 1080, 'fps': 30})
    lead, pad, min_hold, tail = P.get('lead', 0.15), P.get('pad_after', 0.35), P.get('min_hold', 0.4), P.get('tail', 1.2)
    vo_off = P.get('voice_offset', 0.0)
    phrases = (A.get('voice') or {}).get('phrases', [])
    music = A.get('music')
    snap = P.get('snap')
    if snap is None:
        on = (dna.get('audio') or {}).get('cuts_on_beat', '0/0').split('/')
        snap = 'beats' if music and int(on[1] or 0) and int(on[0]) / int(on[1]) >= 0.6 else 'none'
    grid = []
    if music and snap != 'none':
        grid = [b['t'] + P.get('music_offset', 0.0) for b in (music['downbeats'] if snap == 'downbeats' else music['beats'])]
    warns = []
    vo_span = lambda idx: (min(phrases[i]['start'] for i in idx) + vo_off, max(phrases[i]['end'] for i in idx) + vo_off)
    plan = P['scenes']; res = []; t = 0.0
    for k, ps in enumerate(plan):
        r = ref.get(ps['ref'])
        if r is None:
            sys.exit(f"{ps['id']}: scène de référence {ps['ref']} absente de l'ADN")
        D = r['duration']; ph = r['phases']; in_end, out_start = ph['in_end'], ph['out_start']; out_len = D - out_start
        fixed = in_end + out_len
        rhythm = None
        if r.get('rhythmic'):
            # rhythmic scene: as many items as the user gives, at the reference interval, re-snapped on the new tempo
            rr = r['rhythmic']; every = rr['every_s']
            ref_beat = (dna.get('audio') or {}).get('beat_s')
            if music and ref_beat:
                mult = max(1, round(every / ref_beat)) if abs(every / ref_beat - round(every / ref_beat)) < 0.2 else None
                if mult:
                    every = music['beat_s'] * mult
            n = int(ps.get('items', rr['count']))
            rhythm = {'every_s': round(every, 4), 'ref_every_s': rr['every_s'], 'count': n, 'first_rel': rr['first_rel'], 'element': rr['element'],
                      'ease': rr['ease'], 'duration_s': rr['duration_s']}
            fixed = rr['first_rel'] + n * every + out_len
        idx = [i for i in ps.get('vo', []) if i < len(phrases)]
        if len(idx) < len(ps.get('vo', [])):
            warns.append(f"{ps['id']}: phrases de voix {ps['vo']} demandées, {len(phrases)} détectées")
        start = t
        if 'duration' in ps:
            end = start + ps['duration']
        elif idx:
            v0, v1 = vo_span(idx)
            if v0 - lead < start - 1e-6 and k > 0:
                warns.append(f"{ps['id']}: la voix commence ({v0:.2f} s) avant la scène ({start:.2f} s) — scène précédente trop longue")
            end = max(start + fixed + min_hold, v1 + pad)
        else:
            end = start + max(D, fixed + min_hold)
        # the next scene must start before its first word
        nxt = plan[k + 1] if k + 1 < len(plan) else None
        limit = None
        if nxt and [i for i in nxt.get('vo', []) if i < len(phrases)]:
            limit = vo_span([i for i in nxt['vo'] if i < len(phrases)])[0] - lead
        if grid and 'duration' not in ps:
            cands = [g for g in grid if g >= end - 0.12 and (limit is None or g <= limit + 1e-6)]
            if cands:
                end = cands[0]
            elif limit is None:
                cands = [g for g in grid if g >= end - 0.12]
                end = cands[0] if cands else end
        if limit is not None and end > limit + 1e-6:
            end = max(limit, start + fixed)
        if end - start < fixed - 1e-6:
            warns.append(f"{ps['id']}: {end - start:.2f} s disponibles pour {fixed:.2f} s d'animation mesurée — "
                         f"la voix est trop dense : regrouper des phrases ou choisir une scène de référence plus courte")
            end = start + fixed
        if nxt is None:
            if idx:
                end = max(end, vo_span(idx)[1] + tail)
            if phrases:
                end = max(end, phrases[-1]['end'] + vo_off + tail)
        newD = end - start
        hold_new = newD - fixed
        if rhythm:  # no stretch: reference-local time runs at speed 1; the recipe lays out rhythm['count'] items
            knots = [[0.0, 0.0], [round(newD, 4), round(newD, 4)]]
            if ph['hold'] <= 1e-3:
                hold_new = 0
        elif hold_new >= ph['hold'] - 1e-6:
            # longer hold: linear stretch of the hold only (entrance and exit keep their measured speed)
            knots = [[0.0, 0.0], [round(in_end, 4), round(in_end, 4)], [round(out_start, 4), round(newD - out_len, 4)], [round(D, 4), round(newD, 4)]]
            if hold_new > 1.6 * ph['hold'] and ph['hold'] > 0.3:
                warns.append(f"{ps['id']}: pause étirée x{hold_new / ph['hold']:.1f} — si la référence bouge pendant sa pause, "
                             f"faire vivre la pause (mouvement secondaire continu dans after(t)) plutôt que la ralentir")
        elif r['phases'].get('continuous') and ps.get('hold_mode', 'auto') != 'speed1':
            # the hold is carried by a continuous move (progress bar, slow zoom...): it keeps its proportion of the scene
            knots = [[0.0, 0.0], [round(in_end, 4), round(in_end, 4)], [round(out_start, 4), round(newD - out_len, 4)], [round(D, 4), round(newD, 4)]]
            warns.append(f"{ps['id']}: pause compressée x{hold_new / max(ph['hold'], 1e-6):.2f} — portée par un mouvement continu "
                         f"({', '.join(r['phases']['continuous'])}) qui garde sa proportion ; hold_mode: speed1 pour l'interdire")
        else:
            # shorter hold: NEVER compress (it would speed up whatever moves during the hold): play it at speed 1
            # and skip the rest of it at the start of the exit (step in the knots)
            h = round(in_end + max(0.0, hold_new), 4)
            knots = [[0.0, 0.0], [round(in_end, 4), round(in_end, 4)], [h, h], [round(out_start, 4), h], [round(D, 4), round(newD, 4)]]
        res.append({'id': ps['id'], 'ref': ps['ref'], 'source': r.get('source', dna['meta'].get('source')), 'ref_start': r['start'], 'ref_end': r['end'],
                    'new_start': round(start, 4), 'new_end': round(end, 4), 'duration': round(newD, 4),
                    'knots': knots, 'rhythm': rhythm,
                    'ref_phases': ({'in_end': rhythm['first_rel'], 'out_start': round(rhythm['first_rel'] + rhythm['count'] * rhythm['every_s'], 4),
                                    'duration': round(newD, 4)} if rhythm else {'in_end': in_end, 'out_start': out_start, 'duration': D}), 'hold_factor': round(hold_new / ph['hold'], 3) if ph['hold'] > 1e-3 and not rhythm else None,
                    'vo': [dict(phrases[i], start=round(phrases[i]['start'] + vo_off, 3), end=round(phrases[i]['end'] + vo_off, 3),
                                words=[dict(w, start=round(w['start'] + vo_off, 3), end=round(w['end'] + vo_off, 3)) for w in phrases[i].get('words', [])])
                           for i in idx],
                    'slots': ps.get('slots', {}), 'overlap_in': ps.get('overlap_in', 0.0), 'overlap_out': ps.get('overlap_out', 0.0)})
        t = end
    # a dissolve / wipe into the next scene needs the outgoing scene to stay visible under it
    for i in range(len(res) - 1):
        tr = ref[res[i + 1]['ref']].get('transition_in') or {}
        if tr.get('duration') and not plan[i].get('overlap_out') and any(w in tr.get('type', '') for w in ('fondu', 'dissol', 'volet', 'wipe', 'cross', 'rideau')):
            res[i]['overlap_out'] = tr['duration']
    total = round(t, 4)
    fps = stage['fps']
    # music start: when the voice dictates the cuts, slide the music under them instead — pick where to START reading
    # the music file so that the most cuts land on a beat (+-1 frame), preferring a strong accent / downbeat
    music_start = P.get('music_start')
    if music and music_start is None and snap != 'none' and len(res) > 1:
        cuts = [r_['new_start'] for r_ in res[1:]]
        bt = [b['t'] for b in music['beats']]; down = {round(b['t'], 3) for b in music['downbeats']}
        best = (-1, 0, 0.0)
        for b0 in bt:
            if b0 + total > music['duration'] + 0.01:
                break
            for c0 in cuts[:1]:
                ms = b0 - c0  # music time aligned so that beat b0 falls on the first cut
                if ms < 0:
                    continue
                hit = sum(1 for c in cuts if min(abs(c + ms - x) for x in bt) <= 1.0 / fps + 1e-6)
                strong = sum(1 for c in cuts if any(abs(c + ms - x) <= 1.0 / fps for x in down))
                if (hit, strong, -ms) > best:
                    best = (hit, strong, -ms)
        music_start = round(-best[2], 4)
        warns.append(f"musique démarrée à {music_start:.3f} s dans le fichier : {best[0]}/{len(cuts)} coupes sur un temps "
                     f"({best[1]} sur un premier temps) — finalize.py --music-start {music_start}")
    for s in res:  # cuts on whole frames: no half-frame scene boundaries
        s['new_start_frame'] = round(s['new_start'] * fps); s['new_end_frame'] = round(s['new_end'] * fps)
    if music and music['duration'] + P.get('music_offset', 0.0) < total - 0.05:
        warns.append(f"musique ({music['duration']} s) plus courte que la vidéo ({total} s) : boucler, couper ou rallonger")
    T = {'music_start': music_start, 'stage': stage, 'brand': P.get('brand', {}), 'blur': P.get('blur'), 'finish': P.get('finish', {}), 'total': total, 'total_frames': round(total * fps), 'snap': snap, 'voice_offset': vo_off,
         'music_offset': P.get('music_offset', 0.0), 'scenes': res, 'warnings': warns}
    mk.save_json(T, out)
    js = os.path.splitext(out)[0] + '.js'
    open(js, 'w', encoding='utf-8').write('window.TIMING = ' + json.dumps(T, ensure_ascii=False) + ';\n')
    print(f"vidéo : {total} s ({T['total_frames']} images à {fps} i/s), calage {snap}")
    for s in res:
        hf = (f"rythme {s['rhythm']['count']} x {s['rhythm']['every_s']} s" if s.get('rhythm') else
              (f"pause x{s['hold_factor']}" if s['hold_factor'] else 'sans pause'))
        print(f"  {s['id']:5s} (réf {s['ref']}) {s['new_start']:7.2f}–{s['new_end']:7.2f} s  {hf}  "
              + ' / '.join((p.get('text') or f"phrase {p['i']}")[:40] for p in s['vo']))
    for w in warns:
        print('  ATTENTION', w)
    print('->', out, '+', js)


if __name__ == '__main__':
    main()
