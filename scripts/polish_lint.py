"""Phase 5: the finish check that removes the "made by an AI" look. Run on the FINAL file and the film code.

Usage: python3 polish_lint.py <final.mp4> [--film film.html] [--timing timing.json] [--ref reference.mp4]
                              [--expect 1920x1080] [--lufs -14] [--safe 0.04]
Video
  format       size (16:9 1920x1080 unless asked otherwise), frame rate = timing, H.264 yuv420p
  durée        audio length = video length (+-1 frame), no silent start > 0.5 s when a voice exists
  images mortes  frozen stretches longer than 2.5 s that the reference does not have (holds of the reference
               are allowed, stretched by the warp)
  pops         one-frame jumps outside a cut (an element appearing without any ease)
  scintillement  luminance going up/down/up on 3 consecutive frames
  marges       text/edges inside the outer --safe band on still frames (title-safe area)
  noir         black or blank first/last frame (unless the reference starts that way)
Sound
  loudness     integrated LUFS within +-1.5 of --lufs, true peak <= -1 dBTP
Code (--film)
  non-determinism  Math.random, Date.now, performance.now, requestAnimationFrame, setTimeout/setInterval,
                   CSS transition/animation, repeat: -1  (the frame must be a pure function of t)
  defaults     a tween without an explicit ease, a ".to(" with 0.5 s and no ease, fonts without @font-face/FontFace
Exit code 1 when a blocking problem remains. Each item is fixed or explained in the delivery report.
"""
import os as _o, sys as _s; _s.path.insert(0, _o.path.dirname(_o.path.abspath(__file__))); import _mkpy  # noqa: E401,E702,F401  (bon Python + PATH)
import sys, os, re, json, subprocess
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mkcommon as mk  # noqa: E402


def main():
    a = sys.argv
    if len(a) < 2:
        sys.exit(__doc__)
    vid = a[1]; V = mk.probe(vid); fps = V['fps']
    T = json.load(open(mk.arg(a, 'timing'))) if mk.arg(a, 'timing') else None
    block, warn, okl = [], [], []
    exp = mk.arg(a, 'expect', f"{T['stage']['w']}x{T['stage']['h']}" if T else '1920x1080')
    ew, eh = map(int, exp.split('x'))
    (okl if (V['w'], V['h']) == (ew, eh) else block).append(f"format {V['w']}x{V['h']} (attendu {exp})")
    if T and abs(fps - T['stage']['fps']) > 0.01:
        block.append(f"{fps:g} i/s au lieu de {T['stage']['fps']}")
    st = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'stream=codec_type,codec_name,pix_fmt,duration', '-of', 'json', vid],
                        capture_output=True, text=True).stdout
    S = json.loads(st)['streams']
    vs = next((s for s in S if s['codec_type'] == 'video'), {}); au = next((s for s in S if s['codec_type'] == 'audio'), None)
    if vs.get('codec_name') != 'h264' or vs.get('pix_fmt') != 'yuv420p':
        warn.append(f"codec {vs.get('codec_name')} {vs.get('pix_fmt')} (livraison conseillée : h264 yuv420p)")
    vdur = V['frames'] / fps
    if au is None:
        warn.append('aucune piste audio')
    else:
        ad = float(au.get('duration') or 0)
        (okl if abs(ad - vdur) <= 1.5 / fps else block).append(f'son {ad:.3f} s / image {vdur:.3f} s')
        r = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', vid, '-af', 'ebur128=peak=true', '-f', 'null', '-'], capture_output=True, text=True).stderr
        I = re.findall(r'I:\s+(-?[\d.]+) LUFS', r); P = re.findall(r'Peak:\s+(-?[\d.]+) dBFS', r)
        tgt = mk.arg(a, 'lufs', -14.0, float)
        if I:
            li = float(I[-1]); (okl if abs(li - tgt) <= 1.5 else block).append(f'loudness {li} LUFS (cible {tgt})')
        if P:
            pk = float(P[-1]); (okl if pk <= -0.9 else block).append(f'crête vraie {pk} dBTP (max -1)')
        sil = subprocess.run(['ffmpeg', '-hide_banner', '-i', vid, '-af', 'silencedetect=n=-45dB:d=0.5', '-f', 'null', '-'], capture_output=True, text=True).stderr
        m = re.search(r'silence_start: (-?[\d.]+)\s.*?silence_end: ([\d.]+)', sil, re.S)
        if m and float(m.group(1)) <= 0.05 and T and T['scenes'] and T['scenes'][0]['vo']:
            warn.append(f'silence au début jusqu\'à {float(m.group(2)):.2f} s alors qu\'une voix est prévue')
    print('mesure de la vidéo…')
    C = mk.curves(vid)
    e = C['energy']; L = C['luma']
    cuts = set()
    if T:
        for s in T['scenes'][1:]:
            f = s['new_start_frame']; cuts |= {f - 1, f, f + 1}
    else:
        cuts |= set(mk.local_peaks(C['hist'], 0.35))
    # frozen stretches
    ref_holds = []
    if T and mk.arg(a, 'ref'):
        for s in T['scenes']:
            ph = s['ref_phases']; k = s['knots']
            tn = lambda x: next((p[1] + (x - p[0]) * (q[1] - p[1]) / (q[0] - p[0]) for p, q in zip(k, k[1:]) if p[0] <= x <= q[0] and q[0] > p[0]), x)
            a0, a1 = tn(ph['in_end']), tn(ph['out_start'])
            if a1 - a0 > 2.5:
                ref_holds.append((s['new_start'] + a0, s['new_start'] + a1))
    still = e < max(1e-5, np.median(e) * 0.05)
    run = 0
    for i, v in enumerate(list(still) + [False]):
        if v:
            run += 1
        else:
            if run / fps > 2.5:
                t0, t1 = (i - run) / fps, i / fps
                allowed = any(h0 - 0.2 <= t0 and t1 <= h1 + 0.2 for h0, h1 in ref_holds)
                (warn if allowed else block).append(f'image figée {t0:.2f}–{t1:.2f} s ({run / fps:.1f} s)'
                                                    + (' — pause de la référence étirée : vérifier qu\'un mouvement secondaire la fait vivre' if allowed else ''))
            run = 0
    # one-frame pops
    med = np.median(e[e > 0]) if (e > 0).any() else 1e-6
    pops = [i for i in range(2, len(e) - 2) if i not in cuts and e[i] > 12 * med and e[i - 1] < 3 * med and e[i + 1] < 3 * med]
    if pops:
        warn.append(f"sauts d'une image hors coupe (élément sans ease ?) : {', '.join(f'{p / fps:.2f}s' for p in pops[:10])}")
    fl = [i for i in range(1, len(L) - 2) if i not in cuts and (L[i] - L[i - 1]) * (L[i + 1] - L[i]) < 0 and (L[i + 2] - L[i + 1]) * (L[i + 1] - L[i]) < 0
          and min(abs(L[i] - L[i - 1]), abs(L[i + 1] - L[i])) > 0.04]
    if fl:
        warn.append(f"scintillement : {', '.join(f'{p / fps:.2f}s' for p in fl[:10])}")
    # safe margins on still frames + black first / last
    import cv2
    safe = mk.arg(a, 'safe', 0.04, float)
    cap = cv2.VideoCapture(vid)
    stills = [i for i in range(0, V['frames'], max(1, int(fps / 2))) if i < len(e) and e[i] < np.percentile(e, 40)][:60]
    edge_hits = []
    for i in stills:
        cap.set(cv2.CAP_PROP_POS_FRAMES, i); ok, im = cap.read()
        if not ok:
            continue
        g = cv2.Canny(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY), 60, 160)
        h, w = g.shape; bx, by = int(w * safe), int(h * safe)
        band = np.concatenate([g[:by].ravel(), g[-by:].ravel(), g[:, :bx].ravel(), g[:, -bx:].ravel()])
        if (band > 0).mean() > 0.004:
            edge_hits.append(i / fps)
    if edge_hits:
        warn.append(f"contenu dans la marge de sécurité ({safe:.0%}) : {', '.join(f'{t:.1f}s' for t in edge_hits[:8])} — voulu par la référence ?")
    for name, f in (('première', 0), ('dernière', V['frames'] - 1)):
        cap.set(cv2.CAP_PROP_POS_FRAMES, f); ok, im = cap.read()
        if ok and im.std() < 2:
            warn.append(f'{name} image unie ({im.mean():.0f}) — la référence fait-elle pareil ?')
    cap.release()
    film = mk.arg(a, 'film')
    if film:
        src = open(film, encoding='utf-8').read()
        for pat, msg in [(r'Math\.random\(', 'Math.random (utiliser MK.rng(graine))'), (r'Date\.now\(|performance\.now\(', 'horloge réelle'),
                         (r'requestAnimationFrame', 'requestAnimationFrame'), (r'set(Timeout|Interval)\(', 'setTimeout/setInterval'),
                         (r'transition\s*:', 'transition CSS'), (r'animation\s*:', 'animation CSS'), (r'repeat\s*:\s*-1', 'repeat: -1')]:
            for ln, line in enumerate(src.splitlines(), 1):
                if re.search(pat, line) and 'mkm:allow' not in line:
                    block.append(f'{os.path.basename(film)}:{ln} non déterministe : {msg}')
        for ln, line in enumerate(src.splitlines(), 1):
            if re.search(r'\.(to|from|fromTo)\(', line) and 'ease' not in line and 'play(' not in line and 'mkm:allow' not in line:
                nxt = ' '.join(src.splitlines()[ln:ln + 3])
                if 'ease' not in nxt:
                    warn.append(f'{os.path.basename(film)}:{ln} tween sans ease explicite (GSAP mettrait power1.out par défaut)')
        # every family used must be DECLARED: @font-face, new FontFace('X'), or timing brand.fonts (loaded by mkm.js)
        used = set(re.findall(r"font-family\s*:\s*['\"]?([A-Za-z0-9 _-]+?)['\"]?\s*[,;}]", src))
        used -= {'sans-serif', 'serif', 'monospace', 'system-ui', 'inherit'}
        declared = set(re.findall(r"@font-face[^}]*font-family\s*:\s*['\"]?([A-Za-z0-9 _-]+)", src))
        declared |= set(re.findall(r"new FontFace\(\s*['\"]([^'\"]+)", src))
        tp = mk.arg(sys.argv, 'timing')
        if tp and os.path.exists(tp):
            declared |= {f['family'] for f in (json.load(open(tp)).get('brand') or {}).get('fonts', [])}
        missing = sorted(used - declared)
        if missing:
            block.append('polices utilisées sans déclaration (@font-face / FontFace / brand.fonts) : ' + ', '.join(missing) + ' -> police système')
        elif used:
            okl.append('polices déclarées : ' + ', '.join(sorted(used)))
    print('Contrôle de finition :')
    for x in okl:
        print('  OK        ', x)
    for x in warn:
        print('  À VOIR    ', x)
    for x in block:
        print('  BLOQUANT  ', x)
    print('Finition refusée.' if block else 'Finition validée' + (f' ({len(warn)} points à regarder et justifier).' if warn else '.'))
    sys.exit(1 if block else 0)


if __name__ == '__main__':
    main()
