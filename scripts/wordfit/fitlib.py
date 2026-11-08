"""Mesure de mots par ajustement de gabarit Inter (scènes s2-s5).
Un mot = (texte, graisse, opsz) ; à chaque image on cherche taille fs, origine de plume (x, ligne de base y)
et flou gaussien directionnel (sx, sy) qui reproduisent l'encre de l'original (alpha projeté fond -> encre)."""
import cv2, numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.optimize import minimize
D = '/home/user/projets/master-skills-launch/decal/'
FONT = D + 'fonts/Inter[opsz,wght].ttf'
MINT = np.array([182, 254, 0.]); DARK = np.array([38, 38, 0.]); WHITE = np.array([255, 255, 255.])
INK = {'w': WHITE, 'm': MINT, 'd': DARK, 'p': np.array([115., 111., 245.]), 'y': np.array([62., 194., 230.]), 'b': np.array([228., 123., 61.])}   # BGR ; p/y/b = encres des boutons néon (s6)
_fr = {}; _bg = {}; _fonts = {}

def frame(f):
    if f not in _fr:
        im = cv2.imread(D + 'analysis/s2/fr/%04d.png' % f)
        if im is None:   # image hors de la plage extraite : lue dans la vidéo (lecture exacte vérifiée)
            c = cv2.VideoCapture(D + 'src/ref4.mp4'); c.set(cv2.CAP_PROP_POS_FRAMES, f); ok, im = c.read()
        _fr[f] = im.astype(np.float64)
    return _fr[f]

def bgplate(f):
    if f not in _bg:
        b = cv2.imread(D + 'assets/s2_bg/%04d.jpg' % (f + 1))
        if b is None: b = cv2.imread(D + 'assets/bg/%04d.jpg' % (f + 1))   # plaques communes au-delà de 291
        _bg[f] = cv2.resize(b, (736, 414), interpolation=cv2.INTER_LINEAR).astype(np.float64)
    return _bg[f]

def alpha(f, roi, ink, bg='plate'):
    """alpha d'encre (0-1). Sur fond sombre (plaque), blanc et menthe sont résolus ENSEMBLE (moindres carrés 2 couleurs,
    sinon un blanc se projette à 115 % sur la menthe) ; sur aplat menthe, encre sombre seule."""
    x, y, w, h = roi; o = frame(f)[y:y + h, x:x + w]
    if isinstance(bg, (list, tuple)):   # fond uni mesuré (face de bouton, carte) en RVB
        B = np.array(bg[::-1], float); v = INK[ink] - B
        return np.clip(((o - B) * v).sum(2) / max((v * v).sum(), 1), 0, 1)
    if bg == 'plate':
        B = bgplate(f)[y:y + h, x:x + w]; d = o - B; u = WHITE - B; v = MINT - B
        uu = (u * u).sum(2); vv = (v * v).sum(2); uv = (u * v).sum(2); du = (d * u).sum(2); dv = (d * v).sum(2)
        det = np.maximum(uu * vv - uv * uv, 1e-6)
        aw = (du * vv - dv * uv) / det; am = (dv * uu - du * uv) / det
        nw = aw < 0; nm = am < 0
        aw = np.where(nm, du / np.maximum(uu, 1), aw); am = np.where(nw, dv / np.maximum(vv, 1), am)
        aw = np.where(nw, 0, aw); am = np.where(nm, 0, am)
        r = {'w': aw, 'm': am}.get(ink)
        if r is None:
            vv_ = INK[ink] - B; r = (d * vv_).sum(2) / np.maximum((vv_ * vv_).sum(2), 1)
        return np.clip(r, 0, 1)
    B = np.broadcast_to(MINT if bg == 'mint' else np.array(bg, float), o.shape)
    v = INK[ink] - B; a = ((o - B) * v).sum(2) / np.maximum((v * v).sum(2), 1)
    return np.clip(a, 0, 1)

def font(wght, opsz, size):
    k = (wght, opsz, round(size, 2))
    if k not in _fonts:
        ft = ImageFont.truetype(FONT, max(1.0, size)); ft.set_variation_by_axes([opsz, wght]); _fonts[k] = ft
        if len(_fonts) > 4000: _fonts.clear()
    return _fonts.get(k) or font(wght, opsz, size)

def render(text, wght, opsz, fs, px, py, W, H, sx=0, sy=0, ss=4):
    """alpha 0-1 (H, W) ; plume en (px, py) = ligne de base gauche, coordonnées du ROI."""
    im = Image.new('L', (W * ss, H * ss), 0)
    ImageDraw.Draw(im).text((px * ss, py * ss), text, font=font(wght, opsz, fs * ss), fill=255, anchor='ls')
    a = cv2.resize(np.asarray(im, np.float64) / 255, (W, H), interpolation=cv2.INTER_AREA)
    if sx > 0.3 or sy > 0.3:
        a = cv2.GaussianBlur(a, (0, 0), sigmaX=max(sx, 0.01), sigmaY=max(sy, 0.01))
    return a

def inkbox(text, wght, opsz, fs):
    """boîte d'encre relative à la plume (gauche, haut, largeur, hauteur) à la taille fs."""
    ft = font(wght, opsz, fs * 8); l, t, r, b = ft.getbbox(text, anchor='ls')
    return [l / 8, t / 8, (r - l) / 8, (b - t) / 8]

def fit(f, roi, text, ink, wght, opsz, init, bg='plate', blur=False, wmask=None, iters=300):
    """init = [fs, X, Y] en coordonnées image ; renvoie dict fs, x, y, sx, sy, err."""
    A = alpha(f, roi, ink, bg); x0, y0, W, H = roi
    M = np.ones_like(A) if wmask is None else wmask
    def loss(p):
        fs, X, Y = p[:3]; sx, sy = (abs(p[3]), abs(p[4])) if blur else (0, 0)
        if fs < 3: return 1e9
        T = render(text, wght, opsz, fs, X - x0, Y - y0, W, H, sx, sy)
        return float((((A - T) ** 2) * M).sum())
    p0 = list(init) + ([1.0, 1.0] if blur and len(init) == 3 else [])
    r = minimize(loss, p0, method='Nelder-Mead', options={'xatol': 0.02, 'fatol': 1e-3, 'maxiter': iters,
                 'initial_simplex': None})
    p = r.x; out = {'fs': float(p[0]), 'x': float(p[1]), 'y': float(p[2]), 'err': float(r.fun) / max(1, (A > 0.05).sum())}
    if blur: out['sx'], out['sy'] = float(abs(p[3])), float(abs(p[4]))
    return out

def coarse(f, roi, text, ink, wght, opsz, fs, bg='plate', step=1.0, rng=8, center=None):
    """recherche grossière de la position (x, y) par corrélation à taille fixe."""
    A = alpha(f, roi, ink, bg); x0, y0, W, H = roi
    l, t, w, h = inkbox(text, wght, opsz, fs)
    T = render(text, wght, opsz, fs, -l + 2, -t + 2, int(w + 5), int(h + 5))
    if T.shape[0] > A.shape[0] or T.shape[1] > A.shape[1]: return None
    R = cv2.matchTemplate(A.astype(np.float32), T.astype(np.float32), cv2.TM_SQDIFF)
    _, _, mn, _ = cv2.minMaxLoc(R)
    return [fs, x0 + mn[0] - (-l + 2), y0 + mn[1] - (-t + 2)]

# ---- mots en plusieurs « runs » (lettres d'un logo à espacement propre) ----
def render_runs(runs, offs, wght, opsz, fs, px, py, W, H, sx=0, sy=0, ss=4):
    """offs = décalage de chaque run en em (fraction de fs) depuis la plume du mot."""
    im = Image.new('L', (W * ss, H * ss), 0); dr = ImageDraw.Draw(im); ft = font(wght, opsz, fs * ss)
    for r, o in zip(runs, offs):
        dr.text(((px + o * fs) * ss, py * ss), r, font=ft, fill=255, anchor='ls')
    a = cv2.resize(np.asarray(im, np.float64) / 255, (W, H), interpolation=cv2.INTER_AREA)
    if sx > 0.3 or sy > 0.3:
        a = cv2.GaussianBlur(a, (0, 0), sigmaX=max(sx, 0.01), sigmaY=max(sy, 0.01))
    return a

def natural_offs(runs, wght, opsz):
    ft = font(wght, opsz, 1000); o, x = [], 0.0
    for r in runs:
        o.append(x / 1000); x += ft.getlength(r)
    return o

def fit_offs(f, roi, runs, ink, wght, opsz, fs, X, Y, bg='plate'):
    """clé : ajuste fs, Y et la plume de chaque run (offsets libres) ; renvoie fs, X, Y, offs (em)."""
    A = alpha(f, roi, ink, bg); x0, y0, W, H = roi; n = len(runs)
    o0 = natural_offs(runs, wght, opsz)
    def loss(p):
        fs_, Y_ = p[0], p[1]; xs = p[2:]
        T = render_runs(runs, [(x - xs[0]) / fs_ for x in xs], wght, opsz, fs_, xs[0] - x0, Y_ - y0, W, H)
        return float(((A - T) ** 2).sum())
    p0 = [fs, Y] + [X + o * fs for o in o0]
    r = minimize(loss, p0, method='Powell', options={'xtol': 0.01, 'ftol': 1e-5, 'maxiter': 4000})
    r = minimize(loss, r.x, method='Nelder-Mead', options={'xatol': 0.01, 'fatol': 1e-4, 'maxiter': 3000})
    p = r.x; xs = p[2:]
    return {'fs': float(p[0]), 'x': float(xs[0]), 'y': float(p[1]), 'offs': [float((x - xs[0]) / p[0]) for x in xs],
            'err': float(r.fun) / max(1, (A > 0.05).sum())}

def fit_rigid(f, roi, runs, offs, ink, wght, opsz, init, bg='plate', blur=False, wmask=None, iters=400, fixfs=None):
    """par image : fs, X, Y (+ sx, sy) avec offsets fixes."""
    A = alpha(f, roi, ink, bg); x0, y0, W, H = roi
    M = np.ones_like(A) if wmask is None else wmask
    def unpack(p):
        if fixfs: return (fixfs, p[0], p[1]) + ((abs(p[2]), abs(p[3])) if blur else (0, 0))
        return (p[0], p[1], p[2]) + ((abs(p[3]), abs(p[4])) if blur else (0, 0))
    def loss(p):
        fs, X, Y, sx, sy = unpack(p)
        if fs < 3: return 1e9
        T = render_runs(runs, offs, wght, opsz, fs, X - x0, Y - y0, W, H, sx, sy)
        return float((((A - T) ** 2) * M).sum())
    p0 = (list(init[1:3]) if fixfs else list(init[:3])) + ([init[3], init[4]] if blur and len(init) >= 5 else ([1.5, 1.5] if blur else []))
    r = minimize(loss, p0, method='Nelder-Mead', options={'xatol': 0.01, 'fatol': 1e-4, 'maxiter': iters})
    fs, X, Y, sx, sy = unpack(r.x)
    out = {'fs': float(fs), 'x': float(X), 'y': float(Y), 'err': float(r.fun) / max(1, (A > 0.05).sum())}
    if blur: out['sx'], out['sy'] = float(sx), float(sy)
    return out

# ---- rectangles arrondis (pilules, panneaux) ----
def render_rect(x, y, w, h, r, W, H, sx=0, sy=0, ss=4, ang=0):
    im = np.zeros((H * ss, W * ss), np.uint8)
    if w > 0 and h > 0:
        if ang == 0:
            cv2.rectangle(im, (0, 0), (0, 0), 0)
            p = Image.new('L', (W * ss, H * ss), 0)
            ImageDraw.Draw(p).rounded_rectangle([x * ss, y * ss, (x + w) * ss - 1, (y + h) * ss - 1], radius=max(0, r * ss), fill=255)
            im = np.asarray(p)
    a = cv2.resize(im.astype(np.float64) / 255, (W, H), interpolation=cv2.INTER_AREA)
    if sx > 0.3 or sy > 0.3:
        a = cv2.GaussianBlur(a, (0, 0), sigmaX=max(sx, 0.01), sigmaY=max(sy, 0.01))
    return a

def fit_rect(f, roi, init, ink='m', bg='plate', blur=False, fixr=None, A=None, iters=600):
    """init = [x, y, w, h, r] image ; renvoie x, y, w, h, r (+ sx, sy)."""
    if A is None: A = alpha(f, roi, ink, bg)
    x0, y0, W, H = roi
    def unpack(p):
        q = list(p[:4]) + ([fixr] if fixr is not None else [p[4]]); k = 4 if fixr is not None else 5
        return q + ([abs(p[k]), abs(p[k + 1])] if blur else [0, 0])
    def loss(p):
        x, y, w, h, r, sx, sy = unpack(p)
        T = render_rect(x - x0, y - y0, w, h, r, W, H, sx, sy)
        return float(((A - T) ** 2).sum())
    p0 = list(init[:4]) + ([] if fixr is not None else [init[4]]) + ([1, 1] if blur else [])
    res = minimize(loss, p0, method='Nelder-Mead', options={'xatol': 0.01, 'fatol': 1e-4, 'maxiter': iters})
    x, y, w, h, r, sx, sy = unpack(res.x)
    o = {'x': x, 'y': y, 'w': w, 'h': h, 'r': r, 'err': float(res.fun) / max(1, (A > 0.05).sum())}
    if blur: o['sx'], o['sy'] = sx, sy
    return o

# ---- ajustement général d'un mot : paramètres libres choisis ----
def fitw(A, roi, el, p0, free, M=None, clip=None, iters=500):
    """A = alpha d'encre de l'original sur roi ; el = {runs, offs, wght, opsz} ; p0 = dict fs,x,y,sx,sy,op.
    clip = masque (H, W) multiplicatif du gabarit (pilule, cercle) ; M = poids de la perte."""
    x0, y0, W, H = roi; M = np.ones_like(A) if M is None else M
    base = dict(sx=0.0, sy=0.0, op=1.0, a=0.0); base.update(p0)
    def mk(v):
        q = dict(base); q.update(zip(free, v)); q['sx'] = abs(q['sx']); q['sy'] = abs(q['sy']); q['op'] = min(1.0, abs(q['op'])); return q
    def tmpl(q):
        T = render_runs(el['runs'], el['offs'], el['wght'], el['opsz'], q['fs'], q['x'] - x0, q['y'] - y0, W, H, q['sx'], q['sy']) * q['op']
        if abs(q.get('a', 0)) > 1e-4:
            R = cv2.getRotationMatrix2D((q['x'] - x0, q['y'] - y0), -q['a'], 1.0); T = cv2.warpAffine(T, R, (W, H), flags=cv2.INTER_LINEAR)
        if q.get('gg', 0) > 0:
            T = np.clip(T + cv2.GaussianBlur(T, (0, 0), max(abs(q['gs']), 0.5)) * abs(q['gg']) * (1 - T), 0, 1)
        return T * clip if clip is not None else T
    def loss(v):
        q = mk(v)
        if q['fs'] < 3: return 1e12
        return float((((A - tmpl(q)) ** 2) * M).sum())
    v0 = [base[k] if k not in ('sx', 'sy') else max(base[k], 0.6) for k in free]
    if 'op' in free: v0[free.index('op')] = min(0.95, base['op'])
    r = minimize(loss, v0, method='Nelder-Mead', options={'xatol': 0.01, 'fatol': 1e-4, 'maxiter': iters, 'adaptive': len(free) > 4})
    q = mk(r.x); q['err'] = float(r.fun) / max(1.0, float((A * M > 0.05).sum())); q['T'] = tmpl(q)
    return q

# ---- sprites (logo « lute », pièces non typographiques) ----
_spr = {}
def sprite(path):
    if path not in _spr:
        im = cv2.imread(D + path, cv2.IMREAD_UNCHANGED); _spr[path] = im[:, :, 3].astype(np.float64) / 255
    return _spr[path]

def render_sprite(S, x, y, s, W, H, sx=0, sy=0):
    M = np.float32([[s, 0, x + 0.5 * s - 0.5], [0, s, y + 0.5 * s - 0.5]])
    a = cv2.warpAffine(S, M, (W, H), flags=cv2.INTER_LINEAR, borderValue=0)
    if sx > 0.3 or sy > 0.3:
        a = cv2.GaussianBlur(a, (0, 0), sigmaX=max(sx, 0.01), sigmaY=max(sy, 0.01))
    return a

def fits(A, roi, S, p0, free, M=None, clip=None, iters=500):
    x0, y0, W, H = roi; M = np.ones_like(A) if M is None else M
    base = dict(sx=0.0, sy=0.0, op=1.0, s=1.0); base.update(p0)
    def mk(v):
        q = dict(base); q.update(zip(free, v)); q['sx'] = abs(q['sx']); q['sy'] = abs(q['sy']); q['op'] = min(1.0, abs(q['op'])); return q
    def tmpl(q):
        T = render_sprite(S, q['x'] - x0, q['y'] - y0, q['s'], W, H, q['sx'], q['sy']) * q['op']
        return T * clip if clip is not None else T
    def loss(v):
        q = mk(v); return float((((A - tmpl(q)) ** 2) * M).sum())
    v0 = [base[k] if k not in ('sx', 'sy') else max(base[k], 0.6) for k in free]
    if 'op' in free: v0[free.index('op')] = min(0.95, base['op'])
    r = minimize(loss, v0, method='Nelder-Mead', options={'xatol': 0.01, 'fatol': 1e-4, 'maxiter': iters, 'adaptive': len(free) > 4})
    q = mk(r.x); q['err'] = float(r.fun) / max(1.0, float((A * M > 0.05).sum())); q['T'] = tmpl(q)
    return q

# ---- groupes rigides (pilule-sprite + texte vivant) : similitude par image, comparaison RVB composée ----
def warp_rgba(G, ox, oy, x, y, s, a, W, H, sx=0, sy=0):
    """G (h, w, 4) float 0-1, origine (ox, oy) de G placée en (x, y) image, échelle s, rotation a (deg)."""
    c, sn = np.cos(np.radians(a)) * s, np.sin(np.radians(a)) * s
    M = np.float32([[c, -sn, x - (c * ox - sn * oy)], [sn, c, y - (sn * ox + c * oy)]])
    pm = G.copy(); pm[..., :3] *= pm[..., 3:4]           # prémultiplié
    o = cv2.warpAffine(pm, M, (W, H), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0))
    if sx > 0.3 or sy > 0.3: o = cv2.GaussianBlur(o, (0, 0), sigmaX=max(sx, 0.01), sigmaY=max(sy, 0.01))
    return o

def comp(o, B, op=1.0):
    return B * (1 - o[..., 3:4] * op) + o[..., :3] * 255 * op

def fit_group(f, roi, G, ox, oy, p0, free, iters=600, M=None):
    x0, y0, W, H = roi; O = frame(f)[y0:y0 + H, x0:x0 + W]; B = bgplate(f)[y0:y0 + H, x0:x0 + W]
    Mw = np.ones((H, W, 1)) if M is None else M[..., None]
    base = dict(s=1.0, a=0.0, sx=0.0, sy=0.0, op=1.0); base.update(p0)
    def mk(v):
        q = dict(base); q.update(zip(free, v)); q['sx'] = abs(q['sx']); q['sy'] = abs(q['sy']); q['op'] = min(1, abs(q['op'])); return q
    def loss(v):
        q = mk(v); o = warp_rgba(G, ox, oy, q['x'] - x0, q['y'] - y0, q['s'], q['a'], W, H, q['sx'], q['sy'])
        return float((((comp(o, B, q['op']) - O) / 255) ** 2 * Mw).sum())
    v0 = [base[k] if k not in ('sx', 'sy') else max(base[k], 0.6) for k in free]
    r = minimize(loss, v0, method='Nelder-Mead', options={'xatol': 0.005, 'fatol': 1e-4, 'maxiter': iters, 'adaptive': len(free) > 4})
    q = mk(r.x); q['err'] = float(r.fun) / (W * H); return q
