"""Master King Motion: shared helpers on top of rmcommon (decoding, signal curves, colours, drawing).

Everything here is measurement plumbing used by dissect.py, style_compare.py, polish_lint.py, storyboard.py.
"""
import os as _o, sys as _s; _s.path.insert(0, _o.path.dirname(_o.path.abspath(__file__))); import _mkpy  # noqa: E401,E702,F401  (bon Python + PATH)
import os, sys, json, subprocess
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rmcommon  # noqa: E402,F401
from rmcommon import probe, arg  # noqa: E402,F401


def decode(path, width=320, f0=None, f1=None, gray=False):
    """Yield frames (RGB uint8, or gray) scaled to `width` (even height kept to aspect), frame-accurate."""
    V = probe(path)
    h = int(round(V['h'] * width / V['w'] / 2) * 2)
    vf = [f'scale={width}:{h}:flags=area']
    if f0 is not None:
        vf.insert(0, f"select='between(n\\,{int(f0)}\\,{int(f1) - 1})'")
    pix, ch = ('gray', 1) if gray else ('rgb24', 3)
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', path, '-vf', ','.join(vf), '-vsync', '0',
                          '-f', 'rawvideo', '-pix_fmt', pix, '-'], stdout=subprocess.PIPE)
    n = width * h * ch
    while True:
        b = p.stdout.read(n)
        if len(b) < n:
            break
        a = np.frombuffer(b, np.uint8)
        yield a.reshape(h, width) if gray else a.reshape(h, width, 3)
    p.wait()


def read_frame(path, frame):
    """One full-resolution frame (RGB) by frame number."""
    cap = cv2.VideoCapture(path)
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(frame))
    ok, img = cap.read()
    cap.release()
    if not ok:
        return None
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


def edges(rgb_or_gray):
    g = rgb_or_gray if rgb_or_gray.ndim == 2 else cv2.cvtColor(rgb_or_gray, cv2.COLOR_RGB2GRAY)
    e = cv2.Canny(g, 40, 120).astype(np.float32) / 255
    return cv2.GaussianBlur(e, (0, 0), 1.2)


def hist(rgb):
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    h = cv2.calcHist([hsv], [0, 1, 2], None, [16, 8, 8], [0, 180, 0, 256, 0, 256])
    return cv2.normalize(h, h).flatten()


def curves(path, width=320, f0=None, f1=None):
    """Per-frame signals of a video: motion energy (edges, colour-blind), histogram change (cuts),
    mean luminance, sharpness (Laplacian variance), flat-area grain sigma. Arrays of equal length."""
    E, Hd, L, S, G, Cm = [], [], [], [], [], []
    pe = ph = None
    for rgb in decode(path, width, f0, f1):
        g = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        e = edges(g); h = hist(rgb)
        E.append(0.0 if pe is None else float(np.abs(e - pe).mean()))
        Hd.append(0.0 if ph is None else float(cv2.compareHist(ph, h, cv2.HISTCMP_BHATTACHARYYA)))
        L.append(float(g.mean()) / 255)
        S.append(float(cv2.Laplacian(g, cv2.CV_64F).var()))
        hp = g.astype(np.float32) - cv2.GaussianBlur(g.astype(np.float32), (0, 0), 1.5)
        grad = cv2.GaussianBlur(np.abs(cv2.Sobel(g, cv2.CV_32F, 1, 0)) + np.abs(cv2.Sobel(g, cv2.CV_32F, 0, 1)), (0, 0), 2)
        flat = grad < np.percentile(grad, 40) + 1e-6
        G.append(float(hp[flat].std()) if flat.sum() > 200 else 0.0)
        Cm.append(e.mean())
        pe, ph = e, h
    return {k: np.array(v) for k, v in dict(energy=E, hist=Hd, luma=L, sharp=S, grain=G, edge_density=Cm).items()}


def pulldown(path_or_energy, fps=None):
    """Detect a frame-rate conversion with DUPLICATED frames (e.g. 25 -> 30 i/s: one frame in six repeated, not
    byte-identical after compression, so mpdecimate misses it). Returns None or
    {'period': P, 'phase': k, 'true_fps': fps*(P-1)/P, 'distinct': [source indices kept], 'offset': s}.
    Signature: inside moves, the motion energy drops to ~0 on frames idx = k (mod P), regularly.
    The true time of distinct frame j is offset + j / true_fps (least squares on the kept indices)."""
    E = np.asarray(curves(path_or_energy)['energy'] if isinstance(path_or_energy, str) else path_or_energy, float)
    if fps is None:
        fps = probe(path_or_energy)['fps'] if isinstance(path_or_energy, str) else 30.0
    nb = np.minimum(np.r_[E[1:], 0], np.r_[0, E[:-1]])
    holes = np.where((E < 0.15 * nb) & (nb > E.max() * 0.05))[0]
    if len(holes) < 6:
        return None
    best = None
    for P in range(4, 13):
        cnt = np.bincount(holes % P, minlength=P); k = int(cnt.argmax())
        share = cnt[k] / len(holes)
        if share >= 0.8 and (best is None or share > best[2] or (share == best[2] and P < best[0])):
            best = (P, k, share)
    if not best:
        return None
    P, k, _ = best
    keep = [i for i in range(len(E)) if i % P != k]
    tf = fps * (P - 1) / P
    j = np.arange(len(keep)); off = float(np.mean(np.array(keep) / fps - j / tf))
    return {'period': P, 'phase': k, 'true_fps': tf, 'distinct': keep, 'offset': off}


def strip_pulldown(obj, pd):
    """Remove the DUPLICATED frames of a converted reference (pulldown(): idx = phase mod period) from every
    frame-keyed table ({'112': v, '113': v, ...}) inside obj, in place, so interpolation bridges the real frames
    instead of copying the conversion's stall. Returns the number of keys removed."""
    n = 0
    if isinstance(obj, dict):
        ks = list(obj.keys())
        if len(ks) >= 3 and all(k.lstrip('-').isdigit() for k in ks):
            for k in ks:
                if int(k) % pd['period'] == pd['phase'] and len(obj) > 2:
                    del obj[k]; n += 1
            return n
        for v in obj.values():
            n += strip_pulldown(v, pd)
    elif isinstance(obj, list):
        for v in obj:
            n += strip_pulldown(v, pd)
    return n


def local_peaks(c, thr, gap=3):
    out = []
    for i in range(1, len(c) - 1):
        lo, hi = max(0, i - gap), min(len(c), i + gap + 1)
        if c[i] >= thr and c[i] == c[lo:hi].max():
            if not out or i - out[-1] > gap:
                out.append(i)
    return out


def hexc(rgb):
    return '#' + ''.join(f'{int(v):02X}' for v in rgb)


def palette(frames_rgb, k=6):
    """Dominant colours of a list of frames: [{hex, share, chroma, lum}] by share, each the modal exact colour
    of its cluster (not a mean, which would invent colours present nowhere)."""
    px = np.concatenate([f.reshape(-1, 3) for f in frames_rgb]).astype(np.float32)
    if len(px) > 120000:
        px = px[np.random.default_rng(0).choice(len(px), 120000, replace=False)]
    lab = cv2.cvtColor(px.reshape(-1, 1, 3).astype(np.uint8), cv2.COLOR_RGB2LAB).reshape(-1, 3).astype(np.float32)
    k = min(k, max(1, len(np.unique(px.astype(np.uint8), axis=0))))
    _, lbl, _ = cv2.kmeans(lab, k, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.5), 3, cv2.KMEANS_PP_CENTERS)
    lbl = lbl.ravel(); out = []
    for c in range(k):
        m = px[lbl == c].astype(np.uint8)
        if not len(m):
            continue
        q = (m // 4) * 4
        vals, cnt = np.unique(q, axis=0, return_counts=True)
        mode = vals[cnt.argmax()]
        sel = m[np.all(q == mode, axis=1)]
        col = np.median(sel, axis=0)
        l = cv2.cvtColor(col.reshape(1, 1, 3).astype(np.uint8), cv2.COLOR_RGB2LAB).reshape(3).astype(float)
        out.append({'hex': hexc(col), 'share': round(len(m) / len(px), 4),
                    'chroma': round(float(np.hypot(l[1] - 128, l[2] - 128)), 1), 'lum': round(l[0] / 255 * 100, 1)})
    return sorted(out, key=lambda d: -d['share'])


def roles(pal):
    """Guess colour roles: background = largest share; accent = most chromatic among the rest;
    text = strongest luminance contrast with the background."""
    if not pal:
        return {}
    bg = pal[0]; rest = pal[1:] or pal
    accent = max(rest, key=lambda d: d['chroma'] * (0.3 + min(d['share'], 0.3)))
    text = max(rest, key=lambda d: abs(d['lum'] - bg['lum']))
    return {'background': bg['hex'], 'accent': accent['hex'], 'text': text['hex']}


def grid_density(edge_maps, n=6):
    """Mean edge density on an n x n grid (rows of floats summing to 1): where things are in the frame."""
    acc = np.mean(edge_maps, axis=0)
    h, w = acc.shape
    g = np.array([[acc[r * h // n:(r + 1) * h // n, c * w // n:(c + 1) * w // n].mean() for c in range(n)] for r in range(n)])
    s = g.sum()
    return (g / s if s else g).round(4).tolist()


def save_json(obj, path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    json.dump(obj, open(path, 'w'), indent=1, ensure_ascii=False)


def plot_curves(series, path, w=1400, h_each=90, marks=None, fps=30):
    """Tiny dependency-free line plot: series = [(label, array, (r,g,b))]; marks = frame indices (cuts)."""
    from PIL import Image, ImageDraw
    H = h_each * len(series) + 20
    im = Image.new('RGB', (w, H), (18, 18, 22)); d = ImageDraw.Draw(im)
    n = max(len(a) for _, a, _ in series)
    for i, (lab, a, col) in enumerate(series):
        y0 = 10 + i * h_each; a = np.asarray(a, float)
        top = np.percentile(a, 99.5) if len(a) else 1
        top = top or 1
        pts = [(int(j / max(1, n - 1) * (w - 1)), int(y0 + h_each - 8 - min(1, v / top) * (h_each - 20))) for j, v in enumerate(a)]
        if len(pts) > 1:
            d.line(pts, fill=col, width=1)
        d.text((6, y0), lab, fill=col)
    for m in marks or []:
        x = int(m / max(1, n - 1) * (w - 1)); d.line([(x, 0), (x, H)], fill=(90, 90, 100))
    for s in range(0, int(n / fps) + 1):
        x = int(s * fps / max(1, n - 1) * (w - 1)); d.line([(x, H - 6), (x, H)], fill=(160, 160, 160))
        if s % 5 == 0:
            d.text((x + 2, H - 18), f'{s}s', fill=(160, 160, 160))
    im.save(path)
