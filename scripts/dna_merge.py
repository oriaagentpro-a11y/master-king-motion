"""Fusion mode: merge the DNA of several references into one, each scene keeping its own source video.

Usage: python3 dna_merge.py <out motion_dna.json> A=analysis/A/motion_dna.json C=analysis/C/motion_dna.json ...
Scene ids become "A_S01", "C_S04"...; each scene gets "source" (its reference video) and "ref_key". Element ids are
prefixed too ("A_title") unless they already start with the prefix. Typography / finish / audio are kept per
reference under "refs". plan.json then names scenes "A_S01", "C_S04" and retime / storyboard / style_compare use
the right video for each scene.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mkcommon as mk  # noqa: E402

out = sys.argv[1]
merged = {'meta': {'fusion': True, 'format': None, 'fps': None}, 'refs': {}, 'scenes': [], 'elements': {}, 'rules': [], 'typography': {}, 'finish': {}}
for arg in sys.argv[2:]:
    k, p = arg.split('=', 1); D = json.load(open(p))
    src = D['meta']['source']
    merged['refs'][k] = {'source': src, 'format': D['meta']['format'], 'typography': D.get('typography', {}), 'finish': D.get('finish', {}),
                         'audio': D.get('audio'), 'rules': D.get('rules', [])}
    if merged['meta']['format'] is None:
        merged['meta']['format'] = D['meta']['format']; merged['meta']['fps'] = D['meta']['fps']; merged['meta']['source'] = src
        merged['typography'] = D.get('typography', {}); merged['finish'] = D.get('finish', {}); merged['audio'] = D.get('audio')
    ren = {e: (e if e.startswith(k + '_') else f'{k}_{e}') for e in D['elements']}
    for e, v in D['elements'].items():
        merged['elements'][ren[e]] = dict(v, id=ren[e], ref_key=k)
    for s in D['scenes']:
        merged['scenes'].append(dict(s, id=f"{k}_{s['id']}", ref_key=k, source=src, elements=[ren.get(e, e) for e in s.get('elements', [])]))
    merged['rules'] += [f'[{k}] {r}' for r in D.get('rules', [])]
mk.save_json(merged, out)
open(os.path.splitext(out)[0] + '.js', 'w', encoding='utf-8').write('window.DNA = ' + json.dumps(merged, ensure_ascii=False) + ';\n')
print(f"ADN fusionné : {len(merged['scenes'])} scènes, {len(merged['elements'])} éléments, références {list(merged['refs'])} -> {out}")
