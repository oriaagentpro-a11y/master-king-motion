# Groupe « FRIENDS » (s3) entièrement en code : pilule = rectangle arrondi menthe + lueur (box-shadow), texte Inter 500 vivant.
# 1) base mesurée à l'image 115 (taille, rayon, lueur, angle) ; 2) affinité par image (x, y, s, k, a, flou) en RVB composé.
import json, sys
from fitlib import *
K = 115; LW, LH = 640, 260; LC = (LW / 2, LH / 2)      # repère local de la pilule (centre = LC)
def base_layer(P):
    """RGBA float du groupe non tourné : lueur + pilule + texte, centre de pilule en LC."""
    w, h, r = P['w'], P['h'], P['r']
    m = render_rect(LC[0] - w / 2, LC[1] - h / 2, w, h, r, LW, LH)
    gl = cv2.GaussianBlur(np.roll(m, int(round(P['gdy'])), 0), (0, 0), max(P['gs'], .3)) * P['gg']
    T = render_runs(['FRIENDS'], [0], 500, 14, P['fs'], LC[0] + P['tx'], LC[1] + P['ty'], LW, LH)
    if abs(P['ta']) > 1e-4:
        R = cv2.getRotationMatrix2D((LC[0] + P['tx'], LC[1] + P['ty']), -P['ta'], 1.0); T = cv2.warpAffine(T, R, (LW, LH))
    T = T * m
    a = np.clip(m + gl * (1 - m), 0, 1)
    col = np.where(a[..., None] > 0, MINT / 255, 0) * np.ones((LH, LW, 3))
    col = col * (1 - T[..., None]) + (DARK / 255) * T[..., None]
    return np.dstack([col, a])
def warp(G, q, W, H, x0, y0):
    c, sn = np.cos(np.radians(q['a'])), np.sin(np.radians(q['a'])); s, k = q['s'], q['k']
    A2 = np.array([[c * s, -sn * s * k], [sn * s, c * s * k]]); t = np.array([q['x'] - x0, q['y'] - y0]) - A2 @ np.array(LC)
    pm = G.copy(); pm[..., :3] *= pm[..., 3:4]
    o = cv2.warpAffine(pm, np.float32(np.c_[A2, t]), (W, H), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0))
    if q.get('sx', 0) > 0.3 or q.get('sy', 0) > 0.3: o = cv2.GaussianBlur(o, (0, 0), sigmaX=max(q['sx'], .01), sigmaY=max(q['sy'], .01))
    return o
def loss_rgb(G, q, f, roi):
    x0, y0, W, H = roi; O = frame(f)[y0:y0 + H, x0:x0 + W]; B = bgplate(f)[y0:y0 + H, x0:x0 + W]
    o = warp(G, q, W, H, x0, y0); C = B * (1 - o[..., 3:4]) + o[..., :3] * 255
    return float((((C - O) / 255) ** 2).sum())
if __name__ == '__main__':
    roi = [150, 140, 560, 190]
    # texte à 115 (mesuré : fs 91,16 plume 231,4 / 273,9, angle -0,795) ramené dans le repère local de la pilule
    P = dict(w=462, h=96, r=6, gs=6, gg=0.25, gdy=-4, fs=91.162, tx=0, ty=0, ta=0)
    q = dict(x=425, y=236, s=1, k=1, a=-0.8, sx=0, sy=0)
    def settext(P, q):
        c, sn = np.cos(np.radians(-q['a'])), np.sin(np.radians(-q['a'])); dx, dy = 231.397 - q['x'], 273.876 - q['y']
        P['tx'], P['ty'] = c * dx - sn * dy, sn * dx + c * dy; P['ta'] = -0.795 - q['a']
    KEYS = ['w', 'h', 'r', 'gs', 'gg', 'gdy', 'x', 'y', 'a']
    def L(v):
        P2 = dict(P); q2 = dict(q)
        for k_, x in zip(KEYS, v): (P2 if k_ in P2 else q2)[k_] = x
        P2['r'] = abs(P2['r']); P2['gs'] = abs(P2['gs']); P2['gg'] = abs(P2['gg']); settext(P2, q2)
        return loss_rgb(base_layer(P2), q2, K, roi)
    v0 = [P[k_] if k_ in P else q[k_] for k_ in KEYS]
    r = minimize(L, v0, method='Nelder-Mead', options={'maxiter': 2500, 'xatol': 0.01, 'fatol': 1e-4, 'adaptive': True})
    for k_, x in zip(KEYS, r.x): (P if k_ in P else q)[k_] = float(x)
    P['r'] = abs(P['r']); P['gs'] = abs(P['gs']); P['gg'] = abs(P['gg']); settext(P, q)
    print('base', {k_: round(v, 3) for k_, v in P.items()}, {k_: round(v, 3) for k_, v in q.items()}, 'err', r.fun / (roi[2] * roi[3]), flush=True)
    G = base_layer(P); out = {K: dict(q, err=r.fun / (roi[2] * roi[3]))}
    FREE = ['x', 'y', 's', 'k', 'a', 'sx', 'sy']
    def fitf(f, p0):
        rr = [max(0, int(p0['x'] - 330 * p0['s'])), max(0, int(p0['y'] - 120)), 0, 0]
        rr[2] = min(736, int(p0['x'] + 330 * p0['s'])) - rr[0]; rr[3] = min(414, int(p0['y'] + 120)) - rr[1]
        def mk(v):
            qq = dict(p0); qq.update(zip(FREE, v)); qq['sx'] = abs(qq['sx']); qq['sy'] = abs(qq['sy']); return qq
        best = None
        for st in ([0, 0], [3, 1], [8, 1]):
            v0 = [p0[k_] for k_ in FREE]; v0[5] = max(v0[5], st[0]); v0[6] = max(v0[6], st[1])
            res = minimize(lambda v: loss_rgb(G, mk(v), f, rr), v0, method='Nelder-Mead', options={'xatol': 0.003, 'fatol': 1e-5, 'maxiter': 2000, 'adaptive': True})
            if best is None or res.fun < best.fun: best = res
        qq = mk(best.x); qq['err'] = best.fun / (rr[2] * rr[3]); return qq
    p = out[K]
    for f in list(range(K + 1, 131)) + list(range(K - 1, 102, -1)):
        if f == K - 1: p = out[K]
        qq = fitf(f, p); out[f] = qq; p = qq; print(f, {k_: round(v, 3) for k_, v in qq.items()}, flush=True)
        json.dump({'base': P, 'pivot': [0, 0], 'frames': out}, open(D + 'tracks/s3_friends.json', 'w'))
