"""Assemble la piste rejouée d'une scène (tracks/sN.js) depuis les mesures (mots, formes, plaques).
Usage : python3 build.py sN"""
import json, sys
D = '/home/user/projets/master-skills-launch/decal/'
sc = sys.argv[1]; cfg = json.load(open(D + f'tracks/{sc}_build.json'))
COL = {'w': '#FFFFFF', 'm': '#00FEB6', 'd': '#002626'}
out = {'mint': '#00FEB6', 'bg': {}, 'els': {}}
for f in range(cfg['frames'][0], cfg['frames'][1] + 1): out['bg'][f] = 'plate'
for a, b in cfg.get('mint_bg', []):
    for f in range(a, b + 1): out['bg'][f] = 'mint'
W = {}
for wf in cfg.get('words', []): W.update(json.load(open(D + wf)))
SH = {}
for sf in cfg.get('shapes', []): SH.update(json.load(open(D + sf)))
def clean(p, keys):
    return {k: round(float(p[k]), 3) for k in keys if k in p}
for s in cfg.get('shape_els', []):
    tr = SH[s['src']]; fr = {}
    for f, p in tr.items():
        f = int(f)
        if not (cfg['frames'][0] - 1 <= f <= cfg['frames'][1] + 1): continue
        if p is None: continue
        if p == 'full': p = {'cx': 368, 'cy': 207, 'r': 3000}
        fr[f] = clean(p, ['cx', 'cy', 'r', 'x', 'y', 'w', 'h', 'sx', 'sy', 'a', 'op']) if isinstance(p, dict) else p
        if isinstance(p, dict) and 'q' in p: fr[f]['q'] = [[round(v, 2) for v in c] for c in p['q']]
    out['els'][s['id']] = {'type': s['type'], 'z': s.get('z', 1), 'color': s.get('color', '#00FEB6'), 'frames': fr}
for w in cfg.get('word_els', []):
    m = W[w['src']]; fr = {}
    for f, p in m['frames'].items():
        f = int(f)
        if not (cfg['frames'][0] <= f <= cfg['frames'][1]) or p is None: continue
        if w.get('range') and not (w['range'][0] <= f <= w['range'][1]): continue
        fr[f] = clean(p, ['fs', 'x', 'y', 'sx', 'sy', 'op', 's'])
        if fr[f].get('op', 1) < 0.03: del fr[f]
    for f, p in w.get('override', {}).items(): fr[int(f)] = p
    if w.get('clip_frames'):
        a_, b_ = w['clip_frames']
        for f in fr: fr[f]['clip'] = w['clip'] if a_ <= f <= b_ else ''
    if 'sprite' in m:
        out['els'][w['id']] = {'type': 'sprite', 'z': w.get('z', 3), 'src': '../' + w.get('src_img', m['sprite']), 'clip': w.get('clip'), 'frames': fr}
    else:
        out['els'][w['id']] = {'type': 'text', 'z': w.get('z', 3), 'runs': m['runs'], 'offs': [round(o, 5) for o in m['offs']], 'wght': m['wght'],
                               'opsz': m['opsz'], 'color': w.get('color', COL[m['ink']]), 'clip': w.get('clip'), 'frames': fr}
def css_bg(rad, lin):
    n = len(rad); rad = [rad[1] if (i == 0 and min(rad[0]) > 240) else c for i, c in enumerate(rad)]
    L = ', '.join(f'rgba({round(c[0])},{round(c[1])},{round(c[2])},0.5) {100 * (j + .5) / n:.1f}%' for j, c in enumerate(lin))
    R = ', '.join(f'rgb({round(c[0])},{round(c[1])},{round(c[2])}) {100 * (i + .5) / n:.1f}%' for i, c in enumerate(rad))
    return f'linear-gradient(to bottom, {L}), radial-gradient(ellipse farthest-side at 50% 50%, {R})'
for c in cfg.get('coins', []):
    FA = json.load(open(D + c['faces'])); T = json.load(open(D + c['src']))[c['key']]
    fr = {}
    for f, q in T.items():
        f = int(f)
        if not (cfg['frames'][0] <= f <= cfg['frames'][1]) or not (c['range'][0] <= f <= c['range'][1]): continue
        fr[f] = {k: round(float(q[k]), 3) for k in ('cx', 'cy', 'w', 'h', 'sx', 'sy') if k in q}
        fr[f]['face'] = 'logo' if f >= c['logo_from'] else 'glass'
    for f, q in c.get('override', {}).items(): fr[int(f)] = q
    out['els'][c['id']] = {'type': 'coin', 'z': c.get('z', 2), 'bgGlass': css_bg(*FA['glass']), 'bgLogo': css_bg(FA[c['key']]['rad'], FA[c['key']]['lin']),
                           'logo': FA[c['key']]['logo'], 'frames': fr}
for v in cfg.get('vecs', []):
    P = json.load(open(D + v['src']))
    fr = {int(f): q for f, q in P.items() if cfg['frames'][0] <= int(f) <= cfg['frames'][1] and (not v.get('range') or v['range'][0] <= int(f) <= v['range'][1])}
    out['els'][v['id']] = {'type': 'vec', 'z': v.get('z', 4), 'frames': fr}
for pl in cfg.get('plates', []):
    P = json.load(open(D + pl['src']))
    fr = {int(f): v for f, v in P.items() if cfg['frames'][0] <= int(f) <= cfg['frames'][1]}
    out['els'][pl['id']] = {'type': 'plate', 'z': pl.get('z', 5), 'frames': fr}
open(D + f'tracks/{sc}.js', 'w').write(f'window.{sc.upper()}=' + json.dumps(out, separators=(',', ':')) + ';')
print(sc, len(out['els']), 'éléments', {k: len(v['frames']) for k, v in out['els'].items()})
