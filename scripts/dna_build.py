"""Assemble motion_dna.json from the measurements: dissect.json + tracks.json + your annotations.

Usage: python3 dna_build.py <analysis_dir> <out motion_dna.json> [--tracks tracks.json] [--notes notes.json]
- analysis_dir/dissect.json : written by dissect.py (format, scenes, palette, finish, audio)
- tracks.json               : written by track_fit.py (one entry per element, measured moves)
- notes.json                : what only an eye can say, written by Claude after LOOKING at the frames:
    {"scenes": {"S01": {"type": "titre cinétique", "transition_in": {"type": "volet", "duration": 0.4, "ease": "expo.inOut",
                         "source": "mesuré f412-f422"}, "camera": "zoom lent 1.00 -> 1.06", "merge_with": null,
                         "split_at": [12.4]}},
     "typography": {"font": "Outfit", "weights": [700, 400], "case": "Titre", "tracking_em": -0.02,
                    "title_cap_height_norm": 0.07, "ratio_title_body": 2.4, "source": "font_search.py + track_textbox"},
     "elements": {"title": {"slot": "titre", "kind": "text", "stagger": {"unit": "lettre", "each": 0.03, "source": "mesuré"}}},
     "finish": {"grain": "animé, sigma 2.1", "motion_blur": "obturateur 0.5 sur les glissés rapides"},
     "rules": ["les entrées arrivent toujours de la gauche", "un seul héros par plan"]}
Scenes can be split (split_at, seconds) or merged (merge_with) when dissect.py's cuts do not match the real
structure (a circular wipe is a transition, not a cut).
For each scene the DNA computes its phases from the measured moves: in_end (end of the last entrance move)
and out_start (start of the first exit move). retime.py stretches only the hold between them, so every
measured animation keeps its exact speed in the new video.
"""
import sys, os, json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mkcommon as mk  # noqa: E402


def phases(sc, motions):
    s, e, D = sc['start'], sc['end'], sc['duration']
    # a move lasting most of the scene (progress bar, slow zoom, rotation) is CONTINUOUS: not an entrance
    cont = [m for m in motions if m['duration'] > 0.6 * D]
    short = [m for m in motions if m['duration'] <= 0.6 * D]
    ins = [m['start'] + m['duration'] - s for m in short if s - 0.05 <= m['start'] < s + 0.6 * D]
    outs = [m['start'] - s for m in short if s + 0.6 * D <= m['start'] < e and m['start'] - s > (max(ins) if ins else 0)]
    in_end = min(D, max(ins)) if ins else min(D * 0.35, 1.0)
    out_start = min(outs) if outs else D
    if out_start < in_end:
        out_start = in_end
    src = 'mouvements mesurés' if ins or outs else 'par défaut (aucun mouvement mesuré dans la scène : à vérifier)'
    res = {'in_end': round(in_end, 4), 'out_start': round(out_start, 4), 'hold': round(out_start - in_end, 4), 'source': src}
    if cont:
        res['continuous'] = [f"{m.get('element', '?')}.{m['prop']}" for m in cont]
    return res


def main():
    a = sys.argv
    if len(a) < 3:
        sys.exit(__doc__)
    an, out = a[1], a[2]
    D = json.load(open(os.path.join(an, 'dissect.json')))
    tp = mk.arg(a, 'tracks', os.path.join(an, 'tracks.json')); np_ = mk.arg(a, 'notes', os.path.join(an, 'notes.json'))
    T = json.load(open(tp)) if os.path.exists(tp) else {}
    N = json.load(open(np_)) if os.path.exists(np_) else {}
    fps = D['format']['fps']
    for k, extra in N.get('elements', {}).items():  # eye-checked corrections (patterns, motions...) override the fit
        if k in T:
            T[k] = {**T[k], **extra}
        elif extra.get('appear'):   # element measured by eye only (counter, text swap, layout values...)
            T[k] = {'id': k, 'rest': {}, 'disappear': extra.get('disappear', extra['appear']), **extra}
    scenes = [dict(s) for s in D['scenes']]
    # split / merge requested by the notes
    sn = N.get('scenes', {})
    out_sc = []
    for s in scenes:
        cuts = sorted(sn.get(s['id'], {}).get('split_at', []))
        if not cuts:
            out_sc.append(s); continue
        edges = [s['start']] + [c for c in cuts if s['start'] < c < s['end']] + [s['end']]
        for i in range(len(edges) - 1):
            p = dict(s); p['id'] = f"{s['id']}{'abcdefgh'[i]}"; p['start'], p['end'] = round(edges[i], 4), round(edges[i + 1], 4)
            p['duration'] = round(p['end'] - p['start'], 4); p['f0'], p['f1'] = round(p['start'] * fps), round(p['end'] * fps)
            p['events'] = [e for e in s['events'] if p['start'] <= e['t'] < p['end']]
            p['holds'] = [h for h in s['holds'] if p['start'] <= h[0] < p['end']]
            p['cut_in'] = s['cut_in'] if i == 0 else 'découpe manuelle (notes)'
            out_sc.append(p)
    merged = []
    for s in out_sc:
        tgt = sn.get(s['id'], {}).get('merge_with')
        if tgt and merged and merged[-1]['id'] == tgt:
            m = merged[-1]; m['end'] = s['end']; m['f1'] = s['f1']; m['duration'] = round(m['end'] - m['start'], 4)
            m['events'] += s['events']; m['holds'] += s['holds']
        else:
            merged.append(s)
    allm = [dict(m, element=k) for k, e in T.items() for m in e.get('motions', [])]
    for s in merged:
        note = sn.get(s['id'], {})
        s.update({k: v for k, v in note.items() if k not in ('split_at', 'merge_with')})
        s['elements'] = [k for k, e in T.items() if s['start'] - 0.05 <= e['appear']['t'] < s['end'] or
                         (e['appear']['t'] < s['start'] and e['disappear']['t'] >= s['start'])]
        sm = [m for m in allm if s['start'] - 0.2 <= m['start'] < s['end']]
        # rhythmic scene: a repeated motif covers most of it (one word per beat...). Its length comes from the
        # number of items x the interval, never from stretching (that would slow every pop down).
        for k in s['elements']:
            for pt in T[k].get('patterns', []):
                n_in = sum(1 for m in T[k]['motions'] if m['prop'] == pt['prop'] and s['start'] - 0.05 <= m['start'] < s['end'])
                if 'source' in pt:  # eye-checked motif: its own count is the truth
                    n_in = pt['count']
                if n_in >= 3 and n_in * pt['every_s'] >= 0.5 * s['duration']:
                    s['rhythmic'] = {'element': k, 'prop': pt['prop'], 'every_s': pt['every_s'], 'count': n_in,
                                     'first_rel': round(max(0.0, pt['first'] - s['start']), 4), 'ease': pt['ease'], 'duration_s': pt['duration_s']}
        if note.get('phases'):  # eye-measured phases (with their source) win over the automatic ones
            s['phases'] = dict(note['phases'], hold=round(note['phases']['out_start'] - note['phases']['in_end'], 4))
        elif s.get('rhythmic'):
            r = s['rhythmic']; tail = s['duration'] - (r['first_rel'] + r['count'] * r['every_s'])
            s['phases'] = {'in_end': r['first_rel'], 'out_start': round(s['duration'] - max(0.0, tail), 4), 'hold': 0.0,
                           'mode': 'rythmique', 'source': f"motif répété de {r['element']} ({r['count']} x {r['every_s']} s)"}
        else:
            s['phases'] = phases(s, sm)
        for k in ('f0', 'f1', 'peak_frame'):
            s.pop(k, None)
    elements = {}
    for k, e in T.items():
        e = dict(e); e.update(N.get('elements', {}).get(k, {}))
        for m in e.get('motions', []):
            m.setdefault('source', 'mesuré (track_fit)')
        elements[k] = e
    dna = {'meta': {'source': D['source'], 'format': D['format'], 'aspect': D['aspect'], 'fps': fps,
                    'built_from': ['dissect.json'] + (['tracks.json'] if T else []) + (['notes.json'] if N else [])},
           'finish': {'measured': D['finish'], **({'notes': N['finish']} if 'finish' in N else {})},
           'typography': N.get('typography', {}), 'audio': D.get('audio'), 'rules': N.get('rules', []),
           'global': D.get('global', {}), 'scenes': merged, 'elements': elements}
    src = D['source'] if os.path.exists(D['source']) else None
    pd = mk.pulldown(src) if src else None
    if pd:   # rule 52: a 25 -> 30 i/s conversion repeats 1 frame in 6; never copy that stall into the new film
        n = mk.strip_pulldown(dna['elements'], pd)
        dna['meta']['pulldown'] = {k: v for k, v in pd.items() if k != 'distinct'}
        print(f"source convertie (images dupliquées 1/{pd['period']}, vraie cadence {pd['true_fps']:.3g} i/s) : "
              f"{n} valeurs d'images dupliquées retirées des tables image par image")
    mk.save_json(dna, out)
    open(os.path.splitext(out)[0] + '.js', 'w', encoding='utf-8').write('window.DNA = ' + json.dumps(dna, ensure_ascii=False) + ';\n')
    print(f"ADN : {len(merged)} scènes, {len(elements)} éléments, {len(allm)} mouvements mesurés -> {out}")
    for s in merged:
        p = s['phases']
        print(f"  {s['id']:5s} {s['start']:7.2f}–{s['end']:7.2f} s  entrée jusqu'à +{p['in_end']:.2f} s, sortie dès +{p['out_start']:.2f} s"
              f"  ({len(s['elements'])} éléments, {p['source']})")


if __name__ == '__main__':
    main()
