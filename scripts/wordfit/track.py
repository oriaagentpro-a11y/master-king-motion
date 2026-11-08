"""Suivi mesuré des mots d'une scène (s2-s5) : gabarit Inter ajusté à chaque image.
Usage : python3 track.py spec.json out.json [ids...]
spec : {"shapes": "tracks/sX_shapes.json", "els": [{id, text, wght, opsz, ink, bg, key, range, box, clip, letters, free}]}
Sortie : {id: {runs, offs, wght, opsz, ink, frames: {f: {fs, x, y, sx, sy, op, err}}}}"""
import sys, json, os
from fitlib import *
from shapes_s2 import disk
spec = json.load(open(sys.argv[1])); outp = sys.argv[2]; only = sys.argv[3:]
SH = json.load(open(D + spec['shapes'])) if spec.get('shapes') else {}
res = json.load(open(outp)) if os.path.exists(outp) else {}

def clipmask(name, f):
    if not name: return None
    sh = SH.get(name, {}).get(str(f))
    if sh is None: return np.zeros((414, 736))
    if sh == 'full': return np.ones((414, 736))
    if 'cx' in sh: return disk(sh['cx'], sh['cy'], sh['r'])
    m = render_rect(sh['x'], sh['y'], sh['w'], sh['h'], sh.get('r', 0), 736, 414)
    if sh.get('sx', 0) > 0.3 or sh.get('sy', 0) > 0.3: pass
    return m

def others(f, me, ink):
    """somme des gabarits des autres mots de même encre déjà mesurés à l'image f (pelage)."""
    S = np.zeros((414, 736))
    for e in spec['els']:
        if e['id'] == me or e['ink'] != ink or e['id'] not in res: continue
        p = res[e['id']]['frames'].get(str(f))
        if not p: continue
        r = res[e['id']]; x, y = p['x'], p['y']
        if 'sprite' in r:
            S += render_sprite(sprite(r['sprite']), x, y, p.get('s', 1), 736, 414, p.get('sx', 0), p.get('sy', 0)) * p.get('op', 1); continue
        S += render_runs(r['runs'], r['offs'], r['wght'], r['opsz'], p['fs'], x, y, 736, 414, p.get('sx', 0), p.get('sy', 0)) * p.get('op', 1)
    return S

def roi_of(el, p, margin=26):
    if 'sprite' in el:
        S_ = sprite(el['sprite']); h, w = S_.shape; mx = margin + 3 * p.get('sx', 0); my = margin + 3 * p.get('sy', 0)
        x0 = int(max(0, p['x'] - mx)); y0 = int(max(0, p['y'] - my)); x1 = int(min(736, p['x'] + w * p.get('s', 1) + mx)); y1 = int(min(414, p['y'] + h * p.get('s', 1) + my))
        return [x0, y0, max(8, x1 - x0), max(8, y1 - y0)]
    l, t, w, h = inkbox(''.join(el['runs']), el['wght'], el['opsz'], p['fs'])
    w = max(w, (el['offs'][-1] * p['fs'] + inkbox(el['runs'][-1], el['wght'], el['opsz'], p['fs'])[2]) if el['offs'] else w)
    mx = margin + 3 * p.get('sx', 0); my = margin + 3 * p.get('sy', 0)
    x0 = int(max(0, p['x'] + l - mx)); y0 = int(max(0, p['y'] + t - my))
    x1 = int(min(736, p['x'] + l + w + mx)); y1 = int(min(414, p['y'] + t + h + my))
    return [x0, y0, max(8, x1 - x0), max(8, y1 - y0)]

def measure(e, f, p, free):
    el = res[e['id']]; roi = roi_of(el, p); x0, y0, W, H = roi
    if x0 >= 736 or y0 >= 414 or W < 8 or H < 8: return None
    A = alpha(f, roi, e['ink'], e['bg']) - others(f, e['id'], e['ink'])[y0:y0 + H, x0:x0 + W]
    A = np.clip(A, 0, 1)
    cf = e.get('clip_frames'); cname = e.get('clip') if (not cf or cf[0] <= f <= cf[1]) else None
    cm = clipmask(cname, f); clip = cm[y0:y0 + H, x0:x0 + W] if cm is not None else None
    M = None
    if e['bg'] == 'mint' and clip is not None and cname: M = (clip > 0.02).astype(float)
    if e.get('mask'):
        M = np.ones_like(A) if M is None else M
        for (mx, my, mw, mh) in e['mask']:
            M[max(0, my - y0):max(0, my + mh - y0), max(0, mx - x0):max(0, mx + mw - x0)] = 0
    # recentrage grossier (mouvements rapides) : corrélation avec le gabarit précédent
    q0 = dict(p)
    if 'sprite' in el:
        S_ = sprite(el['sprite'])
        fr_ = [k for k in free if k != 'fs'] + (['s'] if 'fs' in free else [])
        q = fits(A, roi, S_, p, fr_, M=M, clip=clip)
        if q['err'] > 0.01 and 'sx' in fr_:
            for sx0 in (3, 6, 10):
                p2 = dict(p); p2['sx'] = sx0; p2['op'] = 1.0; q2 = fits(A, roi, S_, p2, fr_, M=M, clip=clip)
                if q2['err'] < q['err']: q = q2
        q.pop('T', None); return {k: float(v) for k, v in q.items()}
    if e.get('coarse', True):
        T = render_runs(el['runs'], el['offs'], el['wght'], el['opsz'], p['fs'], p['x'] - x0, p['y'] - y0, W, H, p.get('sx', 0), p.get('sy', 0))
        ys, xs = np.where(T > 0.05)
        if len(xs) > 10:
            a0, a1, b0, b1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1; tt = T[a0:a1, b0:b1].astype(np.float32)
            pad = 14; Ap = np.pad(A, pad).astype(np.float32)
            if tt.shape[0] < Ap.shape[0] and tt.shape[1] < Ap.shape[1]:
                R = cv2.matchTemplate(Ap, tt, cv2.TM_SQDIFF); _, _, mn, _ = cv2.minMaxLoc(R)
                q0['x'] = p['x'] + (mn[0] - pad - b0); q0['y'] = p['y'] + (mn[1] - pad - a0)
    q = fitw(A, roi, el, q0, free, M=M, clip=clip)
    if q0 is not p:
        q2 = fitw(A, roi, el, p, free, M=M, clip=clip)
        if q2['err'] < q['err']: q = q2
    if q['err'] > 0.01 and 'sx' in free:
        for sx0 in (3, 6, 10):
            p2 = dict(q0); p2['sx'] = sx0; p2['op'] = 1.0; q2 = fitw(A, roi, el, p2, free, M=M, clip=clip)
            if q2['err'] < q['err']: q = q2
    q.pop('T', None); return {k: float(v) for k, v in q.items()}

for e in spec['els']:
    if only and e['id'] not in only: continue
    if 'sprite' in e:
        res[e['id']] = {'sprite': e['sprite'], 'ink': e['ink'], 'frames': {}}; el = res[e['id']]; k = e['key']
        p = {'x': e['origin'][0], 'y': e['origin'][1], 's': 1.0}
        q = measure(e, k, p, ['x', 'y', 's']); el['frames'][str(k)] = q; print(e['id'], k, q)
        free = e.get('free', ['fs', 'x', 'y', 'sx', 'sy', 'op'])
        for d in (1, -1):
            p = q; f = k + d
            while e['range'][0] <= f <= e['range'][1]:
                if str(f) in e.get('hint', {}):
                    h_ = e['hint'][str(f)]; p = dict(p); p['x'], p['y'] = h_[0], h_[1]
                    if len(h_) > 2: p['sx'], p['sy'] = h_[2], h_[3]
                r = measure(e, f, p, free); el['frames'][str(f)] = r; print(e['id'], f, {a: round(b, 3) for a, b in r.items()}); p = r; f += d
        json.dump(res, open(outp, 'w')); continue
    runs = list(e['text']) if e.get('letters') else ([e['text']] if isinstance(e['text'], str) else e['text'])
    res[e['id']] = {'runs': runs, 'offs': natural_offs(runs, e['wght'], e['opsz']), 'wght': e['wght'], 'opsz': e['opsz'],
                    'ink': e['ink'], 'frames': {}}
    el = res[e['id']]; k = e['key']; bx = e['box']
    l, t, w, h = inkbox(e['text'] if isinstance(e['text'], str) else ''.join(e['text']), e['wght'], e['opsz'], 100)
    fs = 100 * bx[3] / h; p = {'fs': fs, 'x': bx[0] - l * fs / 100, 'y': bx[1] - t * fs / 100}
    roi = [max(0, bx[0] - 6), max(0, bx[1] - 6), bx[2] + 12, bx[3] + 12]
    roi[2] = min(roi[2], 736 - roi[0]); roi[3] = min(roi[3], 414 - roi[1])
    if len(runs) > 1 and e.get('fit_offs', True):
        r = fit_offs(k, roi, runs, e['ink'], e['wght'], e['opsz'], p['fs'], p['x'], p['y'], bg=e['bg'])
        el['offs'] = r['offs']; p = {'fs': r['fs'], 'x': r['x'], 'y': r['y']}; print(e['id'], 'offs', [round(v, 4) for v in r['offs']], 'err', round(r['err'], 4))
    free_key = ['fs', 'x', 'y']
    q = measure(e, k, p, free_key); el['frames'][str(k)] = q; print(e['id'], k, {a: round(b, 3) for a, b in q.items()})
    free = e.get('free', ['fs', 'x', 'y', 'sx', 'sy', 'op'])
    if e.get('glow'):
        free = free + ['gs', 'gg']; q = measure(e, k, dict(q, gs=4.0, gg=0.6), ['fs', 'x', 'y', 'gs', 'gg']); el['frames'][str(k)] = q; print('glow', q)
    for d in (1, -1):
        p = q; f = k + d
        while e['range'][0] <= f <= e['range'][1]:
            fr = e.get('free_at', {}).get(str(f), free)
            if str(f) in e.get('hint', {}):
                h_ = e['hint'][str(f)]; p = dict(p); p['x'], p['y'] = h_[0], h_[1]
                if len(h_) > 2: p['sx'], p['sy'] = h_[2], h_[3]
            r = measure(e, f, p, fr)
            if r is None: break
            el['frames'][str(f)] = r; print(e['id'], f, {a: round(b, 3) for a, b in r.items()})
            if r.get('op', 1) < 0.04: break
            p = r; f += d
    json.dump(res, open(outp, 'w'))
