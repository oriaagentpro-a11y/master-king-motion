"""Phase 4: prove the new video moves like the reference — with the user's content, so not pixel by pixel.

Usage: python3 style_compare.py <reference.mp4> <new.mp4> <timing.json> <out_dir> [--no-video] [--brand-colors]
The reference is first REPLAYED on the new clock (out_dir/reference_recalee.mp4: the warp knots, holds skipped
or stretched, rhythmic scenes item by item on the new tempo) — that is what the new video must follow. Then,
scene by scene, on the same frames:
  rythme    correlation of the motion-energy curves (edges, colour-blind), best lag in +-2 frames   >= 0.70
  événements share of the reference's motion peaks found in the new video at +-1 frame            >= 0.75
  attaque   first significant motion: offset in frames                                               <= 1
  énergie   mean motion energy new / reference (same amount of movement)                       0.5 - 2.0
  mise en page  similarity of the 6x6 edge-density grids (where things are in the frame)          >= 0.70
  lumière   mean luminance difference (ignored with --brand-colors when the palette changes)      <= 0.15
  netteté   motion-blur verdict identical (fast/still sharpness ratio)
  grain     flat-area noise sigma within +-50 % (or both below 0.8)
Writes out_dir/style_report.json (per scene, values, thresholds, verdict, the frames to look at),
out_dir/style_curves.png and out_dir/side_by_side.mp4 (reference at the warped time | new video).
A scene is "conforme" only when every test passes. A high score is not a proof: watch the side-by-side.
"""
import sys, os, json, subprocess
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mkcommon as mk  # noqa: E402

TH = {'rythme': 0.70, 'evenements': 0.75, 'attaque': 1, 'energie': (0.5, 2.0), 'mise_en_page': 0.70, 'lumiere': 0.15, 'grain': 0.5}


def to_new(k, x):
    for i in range(1, len(k)):
        if x <= k[i][0]:
            p, q = k[i - 1], k[i]; sp = q[0] - p[0]
            return q[1] if sp <= 1e-9 else p[1] + (x - p[0]) * (q[1] - p[1]) / sp
    return k[-1][1] + x - k[-1][0]


def to_ref(k, x):
    return to_new([[b, a] for a, b in k], x)


def scene_to_ref(s, tn):
    """Reference-local time shown at new-local time tn: through the knots, or item by item for a rhythmic
    scene (new item i <-> reference item i, wrapped on the reference's item count)."""
    r = s.get('rhythm')
    if r:
        ref_every = r.get('ref_every_s', r['every_s']); first = r['first_rel']
        if tn < first:
            return tn
        i = int((tn - first) // r['every_s']); within = tn - first - i * r['every_s']
        n_ref = max(1, int(round((s['ref_end'] - s['ref_start'] - first) / ref_every)))
        return first + (i % n_ref) * ref_every + min(within, ref_every - 1e-3)
    return to_ref(s['knots'], tn)


def warped_reference(ref, T, out, fps):
    """The reference replayed on the NEW clock (what the new video is supposed to follow), reference size."""
    R = mk.probe(ref); w, h = R['w'] // 2 * 2, R['h'] // 2 * 2
    readers = {}
    p = subprocess.Popen(['ffmpeg', '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{w}x{h}', '-r', f'{fps:g}', '-i', '-',
                          '-c:v', 'libx264', '-crf', '14', '-preset', 'veryfast', '-pix_fmt', 'yuv420p', out], stdin=subprocess.PIPE)
    for f in range(T['total_frames']):
        t = f / fps
        s = next((x for x in T['scenes'] if x['new_start_frame'] <= f < x['new_end_frame']), T['scenes'][-1])
        tr = scene_to_ref(s, t - s['new_start'])
        srcv = s.get('source') or ref
        if srcv not in readers:
            readers[srcv] = (Reader(srcv, (w, h)), mk.probe(srcv), mk.pulldown(srcv))
            pd = readers[srcv][2]
            if pd:
                print(f"  {os.path.basename(srcv)} : images dupliquées 1/{pd['period']} (phase {pd['phase']}) -> vraie cadence "
                      f"{pd['true_fps']:.3g} i/s, rejouée sur ses images distinctes")
        rd, R, pd = readers[srcv]
        # fractional reference frame: blend the two neighbours (a 25 -> 30 fps replay would otherwise duplicate one
        # frame in six and fake a "no motion" frame every 0.2 s)
        x = max(0.0, (s['ref_start'] + min(tr, s['ref_end'] - s['ref_start'] - 1 / R['fps'])) * R['fps'])
        if pd:   # pulldown source: interpolate between DISTINCT frames on the true clock (a duplicate = a fake pause)
            D = pd['distinct']; jx = min(max(0.0, (x / R['fps'] - pd['offset']) * pd['true_fps']), len(D) - 1)
            j0 = int(np.floor(jx)); j1 = min(len(D) - 1, j0 + 1); k = jx - j0; f0, f1 = D[j0], D[j1]
        else:
            f0 = min(R['frames'] - 1, int(np.floor(x))); f1 = min(R['frames'] - 1, f0 + 1); k = x - f0
        if k < 0.02 or f1 == f0:
            img = rd.get(f0)
        else:
            a_ = rd.get(f0).astype(np.float32); b_ = rd.get(f1).astype(np.float32)
            img = (a_ * (1 - k) + b_ * k).round().astype(np.uint8)
        p.stdin.write(img.tobytes())
    p.stdin.close(); p.wait()


def corr(a, b):
    a = (a - a.mean()) / (a.std() + 1e-9); b = (b - b.mean()) / (b.std() + 1e-9)
    return float(np.mean(a * b))


def grid_of(path, frames, width=320):
    maps = []
    cap = cv2.VideoCapture(path)
    for f in frames:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(f)); ok, im = cap.read()
        if not ok:
            continue
        im = cv2.resize(im, (width, int(width * im.shape[0] / im.shape[1])), interpolation=cv2.INTER_AREA)
        maps.append(mk.edges(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)))
    cap.release()
    return np.array(mk.grid_density(maps)) if maps else None


class Reader:
    def __init__(self, path, size):
        self.cap = cv2.VideoCapture(path); self.pos = -1; self.img = None; self.size = size

    def get(self, f):
        if f == self.pos - 1 and getattr(self, 'prev', None) is not None:
            return cv2.resize(self.prev, self.size, interpolation=cv2.INTER_AREA)
        if f < self.pos or f > self.pos + 30:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, f); self.pos = f - 1
        while self.pos < f:
            ok, im = self.cap.read()
            if not ok:
                break
            self.pos += 1; self.prev = self.img; self.img = im
        return cv2.resize(self.img, self.size, interpolation=cv2.INTER_AREA) if self.img is not None else np.zeros((self.size[1], self.size[0], 3), np.uint8)


def side_by_side(wref, new, T, out, h=360):
    """Warped reference (already on the new clock) | new video, frame for frame, with the new video's sound."""
    R, N = mk.probe(wref), mk.probe(new)
    rw, nw = int(h * R['w'] / R['h']) // 2 * 2, int(h * N['w'] / N['h']) // 2 * 2
    W = rw + nw + 8
    p = subprocess.Popen(['ffmpeg', '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{h + 28}', '-r', f"{N['fps']:g}",
                          '-i', '-', '-i', new, '-map', '0:v', '-map', '1:a?', '-c:v', 'libx264', '-crf', '20', '-preset', 'veryfast',
                          '-pix_fmt', 'yuv420p', '-shortest', out], stdin=subprocess.PIPE)
    rr, nr = Reader(wref, (rw, h)), Reader(new, (nw, h))
    for f in range(N['frames']):
        t = f / N['fps']
        s = next((x for x in T['scenes'] if x['new_start'] <= t < x['new_end']), T['scenes'][-1])
        canvas = np.full((h + 28, W, 3), 14, np.uint8)
        canvas[28:, :rw] = rr.get(min(f, R['frames'] - 1)); canvas[28:, rw + 8:] = nr.get(f)
        cv2.putText(canvas, f"REFERENCE {s['ref']} (recalee)", (6, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1, cv2.LINE_AA)
        cv2.putText(canvas, f"NOUVEAU {s['id']}  {t:.2f}s", (rw + 14, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (140, 240, 170), 1, cv2.LINE_AA)
        p.stdin.write(canvas.tobytes())
    p.stdin.close(); p.wait()


def main():
    a = sys.argv
    if len(a) < 5:
        sys.exit(__doc__)
    ref, new, T, out = a[1], a[2], json.load(open(a[3])), a[4]
    brand = '--brand-colors' in a
    os.makedirs(out, exist_ok=True)
    R, N = mk.probe(ref), mk.probe(new)
    nf = N['fps']
    wref = os.path.join(out, 'reference_recalee.mp4')
    print('référence rejouée sur la nouvelle horloge…'); warped_reference(ref, T, wref, nf)
    print('mesure des courbes (référence recalée, nouvelle vidéo)…')
    CR, CN = mk.curves(wref), mk.curves(new)
    rf = nf
    hi = lambda c: c > np.percentile(c, 90)
    lo = lambda c: c < np.percentile(c, 30)
    blur_r = float(np.median(CR['sharp'][hi(CR['energy'])]) / (np.median(CR['sharp'][lo(CR['energy'])]) + 1e-6))
    blur_n = float(np.median(CN['sharp'][hi(CN['energy'])]) / (np.median(CN['sharp'][lo(CN['energy'])]) + 1e-6))
    bv = lambda r: 'flou' if r < 0.6 else ('léger' if r < 0.85 else 'net')
    report = {'thresholds': TH, 'scenes': [], 'global': {}, 'reference_recalee': wref}
    allr, alln = [], []
    n_all = min(len(CR['energy']), len(CN['energy']))
    for s in T['scenes']:
        r0, r1 = s['new_start_frame'], min(s['new_end_frame'], n_all)
        idx = np.arange(r0, r1)
        sm = lambda v: np.convolve(v, [0.25, 0.5, 0.25], mode='same') if len(v) > 3 else v
        er = sm(CR['energy'][r0:r1])
        en = sm(CN['energy'][r0:r1])
        e1, e2 = er[1:], en[1:]
        c = max((corr(e1[max(0, L):len(e1) + min(0, L)], e2[max(0, -L):len(e2) - max(0, L)]), L) for L in range(-2, 3)) if len(e1) > 6 else (1.0, 0)
        from scipy.signal import find_peaks
        # events = clear motion peaks (prominence), not the ripples of a smooth continuous move
        pk = lambda v: list(find_peaks(v, prominence=0.25 * v.max(), distance=3)[0]) if len(v) > 3 and v.max() > 0 else []
        pr, pn = pk(e1), pk(e2)
        matched = [p for p in pr if pn and min(abs(q - p) for q in pn) <= 1]
        ev = len(matched) / len(pr) if len(pr) >= 2 else 1.0
        # attack = first MOTION, not the cut: the cut's energy leaks into the next frame through the smoothing (it made
        # a reference "start" at frame 0 while its move started 10 frames later): skip the 2 frames after the cut
        on = lambda v: 2 + int(np.argmax(v[2:] > 0.2 * v[2:].max())) if len(v) > 3 and v[2:].max() > 0 else 0
        att = abs(on(e1) - on(e2))
        ratio = float(e2.mean() / (e1.mean() + 1e-9)) if len(e1) else 1.0
        ks = np.linspace(r0, r1 - 1, 6).astype(int)
        gr = grid_of(wref, ks); gn = grid_of(new, ks)
        lay = float(1 - 0.5 * np.abs(gr - gn).sum()) if gr is not None and gn is not None else None
        lum = abs(float(CR['luma'][r0:r1].mean() - CN['luma'][r0:r1].mean()))
        g_r, g_n = float(np.median(CR['grain'][r0:r1])), float(np.median(CN['grain'][r0:r1]))
        grain_ok = (g_r < 0.8 and g_n < 0.8) or abs(g_n - g_r) <= TH['grain'] * max(g_r, 1e-6)
        tests = {
            'rythme': {'valeur': round(c[0], 3), 'décalage': c[1], 'ok': c[0] >= TH['rythme']},
            'evenements': {'valeur': round(ev, 3), 'référence': len(pr), 'trouvés': len(matched), 'ok': ev >= TH['evenements']},
            'attaque': {'valeur': att, 'ok': att <= TH['attaque']},
            'energie': {'valeur': round(ratio, 3), 'ok': TH['energie'][0] <= ratio <= TH['energie'][1]},
            'mise_en_page': {'valeur': None if lay is None else round(lay, 3), 'ok': lay is None or lay >= TH['mise_en_page']},
            'lumiere': {'valeur': round(lum, 3), 'ok': brand or lum <= TH['lumiere'], **({'ignoré': 'palette de marque'} if brand else {})},
            'grain': {'référence': round(g_r, 2), 'nouveau': round(g_n, 2), 'ok': bool(grain_ok)},
        }
        bad = [k for k, v in tests.items() if not v['ok']]
        worst = []
        if len(e1) > 3:
            dif = np.abs((e1 / (e1.max() + 1e-9)) - (e2 / (e2.max() + 1e-9)))
            worst = [{'new_frame': int(idx[1 + i]), 'new_t': round(idx[1 + i] / nf, 3)} for i in np.argsort(-dif)[:3]]
        report['scenes'].append({'id': s['id'], 'ref': s['ref'], 'tests': tests, 'verdict': 'conforme' if not bad else 'à corriger : ' + ', '.join(bad),
                                 'regarder': worst})
        allr.append(e1); alln.append(e2)
        print(f"  {s['id']:5s} rythme {c[0]:.2f}  événements {len(matched)}/{len(pr)}  attaque {att} img  énergie x{ratio:.2f}  "
              f"mise en page {lay if lay is None else round(lay, 2)}  lumière {lum:.2f}  grain {g_r:.1f}/{g_n:.1f}  -> "
              f"{'conforme' if not bad else 'À CORRIGER ' + ', '.join(bad)}")
    ar, an = np.concatenate(allr), np.concatenate(alln)
    report['global'] = {'rythme': round(corr(ar, an), 3), 'netteté': {'référence': round(blur_r, 3), 'nouveau': round(blur_n, 3),
                        'ok': bv(blur_r) == bv(blur_n), 'verdicts': [bv(blur_r), bv(blur_n)]},
                        'scènes_conformes': f"{sum(s['verdict'] == 'conforme' for s in report['scenes'])}/{len(report['scenes'])}"}
    ok_all = all(s['verdict'] == 'conforme' for s in report['scenes']) and report['global']['netteté']['ok']
    report['verdict'] = 'CONFORME' if ok_all else 'À CORRIGER'
    mk.save_json(report, os.path.join(out, 'style_report.json'))
    mk.plot_curves([('énergie référence (sur l\'horloge de la référence)', ar, (255, 196, 0)), ('énergie nouvelle vidéo (ramenée)', an, (120, 230, 160))],
                   os.path.join(out, 'style_curves.png'), fps=rf)
    if '--no-video' not in a:
        side_by_side(wref, new, T, os.path.join(out, 'side_by_side.mp4'))
    g = report['global']
    print(f"global : rythme {g['rythme']}, netteté {g['netteté']['verdicts']}, scènes conformes {g['scènes_conformes']} -> {report['verdict']}")
    print('->', os.path.join(out, 'style_report.json'))
    sys.exit(0 if ok_all else 1)


if __name__ == '__main__':
    main()
