"""Phase 1 of Master King Motion: dissect a reference video into measured facts (the start of its DNA).

Usage: python3 dissect.py <reference.mp4> <analysis_dir> [--width 320] [--cut 0.35] [--per-scene 6]
Writes in analysis_dir:
  dissect.json         format, cuts, scenes (duration, palette + roles, layout grid, motion energy profile,
                       events, holds, density, blur, grain), global finish (grain, vignette, motion blur), audio
  contact_all.png      timestamped contact sheet of every scene (one row per scene)
  contact_Sxx.png      one sheet per scene (first, entrances, peak motion, hold, last)
  curves.png           motion energy / cuts / luminance / sharpness over time, cuts marked
  beats.json           tempo, beats, accents (only if the reference has a soundtrack)
Nothing here is guessed: every number comes from the frames. The DNA (motion_dna.json) is then completed
element by element with track_*.py + track_fit.py, and validated with dna_check.py.
"""
import sys, os, json, subprocess
import numpy as np
import cv2
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mkcommon as mk  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def sheet(video, frames, fps, path, label_w=None, tile_w=360):
    V = mk.probe(video)
    th = int(tile_w * V['h'] / V['w'])
    im = Image.new('RGB', (tile_w * len(frames), th + 22), (12, 12, 14)); d = ImageDraw.Draw(im)
    for i, (f, tag) in enumerate(frames):
        fr = mk.read_frame(video, f)
        if fr is None:
            continue
        im.paste(Image.fromarray(fr).resize((tile_w, th), Image.LANCZOS), (i * tile_w, 22))
        d.text((i * tile_w + 4, 4), f'{f / fps:.2f}s  f{f}  {tag}', fill=(235, 235, 235))
    im.save(path)
    return im


def main():
    a = sys.argv
    if len(a) < 3:
        sys.exit(__doc__)
    video, out = a[1], a[2]
    width = mk.arg(a, 'width', 320, int); cut_thr = mk.arg(a, 'cut', 0.35, float); per = mk.arg(a, 'per-scene', 6, int)
    os.makedirs(out, exist_ok=True)
    V = mk.probe(video); fps = V['fps']
    print(f"référence : {V['w']}x{V['h']}, {fps:g} i/s, {V['duration']:.2f} s, {V['frames']} images")
    C = mk.curves(video, width)
    n = len(C['energy'])

    # --- cuts: histogram jump that is a local peak, or edge-energy spike far above its neighbourhood
    med = np.median(C['energy']) + 1e-6
    cuts = [i for i in mk.local_peaks(C['hist'], cut_thr, gap=int(fps * 0.25))]
    spikes = [i for i in mk.local_peaks(C['energy'], np.percentile(C['energy'], 99.7), gap=int(fps * 0.25))
              if C['energy'][i] > 8 * med and C['hist'][i] > cut_thr * 0.5]
    cuts = sorted(set(cuts) | set(spikes))
    bounds = [0] + [c for c in cuts if c > fps * 0.3 and c < n - fps * 0.3] + [n]
    bounds = sorted(set(bounds))
    merged = [bounds[0]]
    for b in bounds[1:]:
        if b - merged[-1] >= fps * 0.3 or b == n:
            merged.append(b)
    if len(merged) > 2 and merged[-1] - merged[-2] < fps * 0.3:
        merged.pop(-2)

    # --- global finish
    lo_e = C['energy'] < np.percentile(C['energy'], 30)
    hi_e = C['energy'] > np.percentile(C['energy'], 90)
    blur_ratio = float(np.median(C['sharp'][hi_e]) / (np.median(C['sharp'][lo_e]) + 1e-6)) if hi_e.any() and lo_e.any() else 1.0
    grain = float(np.median(C['grain']))
    # temporal grain: does the noise change every frame? (static flat area diff)
    corners, centres = [], []
    grain_t = []
    prev = None
    for i, rgb in enumerate(mk.decode(video, width)):
        g = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32)
        h, w = g.shape
        cs = [g[:h // 8, :w // 8], g[:h // 8, -w // 8:], g[-h // 8:, :w // 8], g[-h // 8:, -w // 8:]]
        corners.append(np.mean([c.mean() for c in cs])); centres.append(g[3 * h // 8:5 * h // 8, 3 * w // 8:5 * w // 8].mean())
        if prev is not None and lo_e[i]:
            dd = g - prev
            grain_t.append(float(np.median(np.abs(dd))))
        prev = g
    vignette = float(np.median(np.array(corners) / (np.array(centres) + 1e-6)))
    finish = {
        'motion_blur': {'sharpness_ratio_fast_vs_still': round(blur_ratio, 3),
                        'verdict': 'flou de mouvement probable' if blur_ratio < 0.6 else ('léger' if blur_ratio < 0.85 else 'net'),
                        'check': 'confirmer à l\'œil sur les images rapides (contact_Sxx.png, colonne « pic »)'},
        'grain': {'flat_sigma': round(grain, 2), 'temporal_median_diff': round(float(np.median(grain_t)) if grain_t else 0, 2),
                  'verdict': 'grain animé' if grain > 1.2 and grain_t and np.median(grain_t) > 0.6 else ('grain fixe/léger' if grain > 0.8 else 'aucun')},
        'vignette': {'corner_over_centre_luma': round(vignette, 3), 'verdict': 'vignettage' if vignette < 0.88 else 'aucun'},
    }

    # --- scenes
    scenes = []
    for si in range(len(merged) - 1):
        f0, f1 = merged[si], merged[si + 1]
        e = C['energy'][f0 + 1:f1] if f1 - f0 > 2 else C['energy'][f0:f1]
        dur = (f1 - f0) / fps
        thr_ev = max(np.percentile(C['energy'], 75), (e.max() if len(e) else 0) * 0.35)
        ev = [f0 + 1 + i for i in mk.local_peaks(e, thr_ev, gap=max(2, int(fps * 0.08)))]
        still = e < max(med * 0.25, 1e-5)
        holds, s = [], None
        for i, v in enumerate(list(still) + [False]):
            if v and s is None:
                s = i
            if not v and s is not None:
                if (i - s) / fps >= 0.4:
                    holds.append([round((f0 + 1 + s) / fps, 3), round((f0 + 1 + i) / fps, 3)])
                s = None
        idx = np.linspace(f0, f1 - 1, min(8, f1 - f0)).astype(int)
        frs = [mk.read_frame(video, i) for i in idx]
        frs = [cv2.resize(f, (width, int(width * V['h'] / V['w'])), interpolation=cv2.INTER_AREA) for f in frs if f is not None]
        pal = mk.palette(frs)
        emaps = [mk.edges(f) for f in frs]
        prof = np.interp(np.linspace(0, len(e) - 1, 20), np.arange(len(e)), e) if len(e) > 1 else np.zeros(20)
        prof = (prof / (prof.max() + 1e-9)).round(3).tolist()
        peak = int(f0 + 1 + int(np.argmax(e))) if len(e) else f0
        sid = f'S{si + 1:02d}'
        sc = {
            'id': sid, 'f0': int(f0), 'f1': int(f1), 'start': round(f0 / fps, 4), 'end': round(f1 / fps, 4), 'duration': round(dur, 4),
            'cut_in': 'coupe franche' if f0 in cuts and C['hist'][f0] > cut_thr else ('début' if f0 == 0 else 'transition (pic de mouvement)'),
            'palette': pal, 'roles': mk.roles(pal),
            'luma_mean': round(float(C['luma'][f0:f1].mean()), 3),
            'layout_grid_6x6': mk.grid_density(emaps),
            'energy_profile_20': prof,
            'energy_mean': round(float(e.mean()) if len(e) else 0, 5),
            'events': [{'frame': int(f), 't': round(f / fps, 3), 'rel': round((f - f0) / fps, 3), 'strength': round(float(C['energy'][f] / (e.max() + 1e-9)), 2)} for f in ev],
            'events_per_s': round(len(ev) / dur, 2) if dur else 0,
            'holds': holds,
            'peak_frame': peak,
        }
        scenes.append(sc)
        tags = [(f0, 'début')] + [(x['frame'], 'événement') for x in sc['events'][:max(0, per - 4)]] + [(peak, 'pic')]
        if holds:
            tags.append((int(holds[-1][0] * fps) + 1, 'pause'))
        tags.append((max(f0, f1 - 1), 'fin'))
        tags = sorted({f: t for f, t in tags}.items())[:per + 1]
        sheet(video, tags, fps, os.path.join(out, f'contact_{sid}.png'))
        print(f"  {sid} {sc['start']:7.2f}–{sc['end']:7.2f} s ({dur:5.2f} s)  {len(ev):2d} événements  "
              f"fond {sc['roles'].get('background')}  accent {sc['roles'].get('accent')}  {sc['cut_in']}")

    rows = [Image.open(os.path.join(out, f"contact_{s['id']}.png")) for s in scenes]
    if rows:
        W = max(r.width for r in rows); Hh = sum(r.height for r in rows)
        big = Image.new('RGB', (W, Hh), (12, 12, 14)); y = 0
        for r in rows:
            big.paste(r, (0, y)); y += r.height
        big.save(os.path.join(out, 'contact_all.png'))
    mk.plot_curves([('énergie de mouvement', C['energy'], (255, 196, 0)), ('changement d\'histogramme (coupes)', C['hist'], (255, 90, 90)),
                    ('luminance', C['luma'], (180, 180, 255)), ('netteté', C['sharp'], (120, 220, 160))],
                   os.path.join(out, 'curves.png'), marks=merged[1:-1], fps=fps)

    audio = None
    has_audio = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'a', '-show_entries', 'stream=index', '-of', 'csv=p=0', video],
                               capture_output=True, text=True).stdout.strip()
    if has_audio:
        r = subprocess.run([sys.executable, os.path.join(HERE, 'beats.py'), video, os.path.join(out, 'beats.json'), '--fps', str(fps)],
                           capture_output=True, text=True)
        if r.returncode == 0:
            B = json.load(open(os.path.join(out, 'beats.json')))
            cut_t = [m / fps for m in merged[1:-1]]
            bt = [b['t'] for b in B['beats']]
            on_beat = [min(abs(c - x) for x in bt) <= 1.5 / fps for c in cut_t] if bt else []
            audio = {'tempo': B['tempo'], 'beats': len(B['beats']), 'cuts_on_beat': f'{sum(on_beat)}/{len(on_beat)}',
                     'beat_s': round(60 / B['tempo'], 4) if B['tempo'] else None}
            print(f"  musique : {B['tempo']} BPM, coupes sur un temps : {audio['cuts_on_beat']}")

    res = {'source': os.path.abspath(video), 'format': V, 'aspect': round(V['w'] / V['h'], 4),
           'cuts': [{'frame': int(m), 't': round(m / fps, 4)} for m in merged[1:-1]],
           'scenes': scenes, 'finish': finish, 'audio': audio,
           'global': {'events_per_s': round(sum(len(s['events']) for s in scenes) / (n / fps), 2),
                      'mean_shot_s': round(float(np.mean([s['duration'] for s in scenes])), 3),
                      'energy_curve_file': 'energy.json'}}
    mk.save_json(res, os.path.join(out, 'dissect.json'))
    mk.save_json({'fps': fps, 'energy': np.round(C['energy'], 6).tolist(), 'luma': np.round(C['luma'], 4).tolist(),
                  'sharp': np.round(C['sharp'], 2).tolist()}, os.path.join(out, 'energy.json'))
    print(f"{len(scenes)} scènes, finition : flou {finish['motion_blur']['verdict']}, grain {finish['grain']['verdict']}, "
          f"vignettage {finish['vignette']['verdict']} -> {out}/dissect.json")


if __name__ == '__main__':
    main()
