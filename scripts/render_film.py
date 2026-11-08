"""Render the film (or a part of it) frame by frame, in parallel, without sound.

Usage: python3 render_film.py <film.html> <out.mp4> --timing timing.json [--workers 4] [--start s] [--end s]
                              [--frames list] [--stills dir]
- splits the frame range into --workers chunks, renders each chunk with engine/render.mjs (its own Chromium),
  then joins them losslessly (same codec, concat demuxer): out.mp4 is silent, CRF 12 (intermediate quality);
  finalize.py adds the mixed sound and makes the delivery encode.
- --stills dir --frames 12,48,96 : only screenshots of those frames (new timeline), for the storyboard.
Size and frame rate come from timing.json (stage), never from constants.
"""
import sys, os, json, subprocess, tempfile, shutil
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mkcommon as mk  # noqa: E402

RENDER = os.path.join(HERE, '..', 'engine', 'render.mjs')


def stills(film, T, frames, outdir, hash_=None):
    from playwright.sync_api import sync_playwright
    os.makedirs(outdir, exist_ok=True)
    W, H, fps = T['stage']['w'], T['stage']['h'], T['stage']['fps']
    paths = []
    with sync_playwright() as pw:
        b = mk.rmcommon.launch(pw)
        pg = b.new_page(viewport={'width': W, 'height': H}, device_scale_factor=1)
        errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        q = dict(kv.split('=', 1) for kv in (mk.arg(sys.argv, 'query', '') or '').split('&') if '=' in kv)   # e.g. --query r3d=0
        pg.goto(mk.rmcommon.scene_url(film, fps, query=q))
        try:
            pg.wait_for_function('(window.__rm && window.__rm.ready === true) || !!window.__mk_error', timeout=60000)
        except Exception:
            sys.exit('la page ne devient pas prête : ' + '; '.join(errs[:3]))
        if pg.evaluate('window.__mk_error || null'):
            sys.exit('erreur dans le film : ' + pg.evaluate('window.__mk_error'))
        pg.evaluate('document.fonts.ready')
        for f in frames:
            pg.evaluate(f'void window.__rm.seek({f / fps})')
            pg.evaluate('window.__rm.settle ? window.__rm.settle() : null')
            if pg.evaluate('window.__mk_error || null'):
                print(f'ATTENTION image {f} : ' + pg.evaluate('window.__mk_error')); pg.evaluate('window.__mk_error = null')
            p = os.path.join(outdir, f'f{f:05d}.png'); pg.screenshot(path=p); paths.append(p)
        b.close()
        if errs:
            print('erreurs dans la page :', errs[:5])
    return paths


def main():
    a = sys.argv
    if len(a) < 3:
        sys.exit(__doc__)
    film, out = a[1], a[2]
    T = json.load(open(mk.arg(a, 'timing', 'timing.json')))
    W, H, fps = T['stage']['w'], T['stage']['h'], T['stage']['fps']
    if mk.arg(a, 'stills'):
        fr = [int(x) for x in mk.arg(a, 'frames').split(',')]
        ps = stills(film, T, fr, mk.arg(a, 'stills'))
        print(f'{len(ps)} images -> {mk.arg(a, "stills")}')
        return
    s = mk.arg(a, 'start', 0.0, float); e = mk.arg(a, 'end', T['total'], float)
    f0, f1 = round(s * fps), round(e * fps)
    n = max(1, min(mk.arg(a, 'workers', min(4, os.cpu_count() or 2), int), (f1 - f0) // max(1, int(fps))))
    cuts = [f0 + (f1 - f0) * i // n for i in range(n + 1)]
    tmp = tempfile.mkdtemp(prefix='mkm-render-', dir=os.path.dirname(os.path.abspath(out)))
    parts = [os.path.join(tmp, f'part{i:02d}.mp4') for i in range(n)]

    def job(i):
        r = subprocess.run(['node', RENDER, film, parts[i], '--fps', f'{fps:g}', '--w', str(W), '--h', str(H),
                            '--start', repr(cuts[i] / fps), '--end', repr(cuts[i + 1] / fps)], capture_output=True, text=True)
        if r.returncode:
            raise RuntimeError(f'morceau {i} : ' + (r.stderr or r.stdout)[-800:])
        return (r.stdout + r.stderr).strip().splitlines()[-1:]

    print(f'rendu de {f1 - f0} images ({W}x{H}, {fps:g} i/s) en {n} morceaux…')
    with ThreadPoolExecutor(n) as ex:
        for i, msg in enumerate(ex.map(job, range(n))):
            print(f'  morceau {i}: {msg[0] if msg else "ok"}')
    lst = os.path.join(tmp, 'list.txt')
    open(lst, 'w').write(''.join(f"file '{p}'\n" for p in parts))
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', lst, '-c', 'copy', out], check=True)
    shutil.rmtree(tmp, ignore_errors=True)
    V = mk.probe(out)
    ok = V['frames'] == f1 - f0
    print(f"{out} : {V['frames']} images {V['w']}x{V['h']} {'OK' if ok else f'ATTENTION attendu {f1 - f0}'}")
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
