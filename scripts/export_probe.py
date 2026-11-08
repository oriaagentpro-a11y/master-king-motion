"""Export a 3D object's per-frame state from the film (MK.probe) into a Blender job, so the photoreal render follows the
film's validated timing exactly.

Usage: python3 export_probe.py <film.html> <timing.json> <scene id> <probe name> <out job.json> --fov 25
                               [--object icon --face face.png] [--hdri ...] [--samples 64] [--out-frames path/f_####.png]
                               [--hide-css]
                               [--object tokens --kinds coin_fcfa,plane,card,wifi]  (probe = list of {cx, cy, h, rx, ry, rz})
For every frame of the scene (new timeline) the page is seeked and window.__mk_probe[name] = {cx, cy, h, rx, ry, rz}
is read; cx, cy, h (normalised on-screen centre and apparent HEIGHT of the object) are converted to a camera-space pose
for the given vertical fov (object 1 unit tall). Frames where the probe is missing hide the object (pose far away).
"""
import sys, os, json, math

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mkcommon as mk  # noqa: E402


def main():
    a = sys.argv
    if len(a) < 6:
        sys.exit(__doc__)
    film, tp, sid, name, out = a[1:6]
    T = json.load(open(tp)); sc = next(s for s in T['scenes'] if s['id'] == sid)
    W, H, fps = T['stage']['w'], T['stage']['h'], T['stage']['fps']
    fov = mk.arg(a, 'fov', 25, float); th = math.tan(math.radians(fov) / 2)
    from playwright.sync_api import sync_playwright
    frames = []

    def pose_of(v):
        if not v or v.get('h', 0) <= 1e-4:
            return {'x': 0, 'y': 0, 'z': 50, 'rx': 0, 'ry': 0, 'rz': 0}
        z = -1.0 / (v['h'] * 2 * th); vh = 2 * (-z) * th; vw = vh * W / H
        return {'x': round((v['cx'] - 0.5) * vw, 6), 'y': round((0.5 - v['cy']) * vh, 6), 'z': round(z, 6),
                'rx': v.get('rx', 0), 'ry': v.get('ry', 0), 'rz': v.get('rz', 0)}
    with sync_playwright() as pw:
        b = mk.rmcommon.launch(pw); pg = b.new_page(viewport={'width': W, 'height': H})
        pg.goto(mk.rmcommon.scene_url(film, fps, query={'r3d': '0'})); pg.wait_for_function('(window.__rm && window.__rm.ready) || !!window.__mk_error', timeout=60000)
        if pg.evaluate('window.__mk_error || null'):
            sys.exit('erreur dans le film : ' + pg.evaluate('window.__mk_error'))
        for k in range(sc['new_start_frame'], sc['new_end_frame']):
            pg.evaluate(f'void (window.__mk_probe = {{}}, window.__rm.seek({k / fps}))')
            v = pg.evaluate(f'window.__mk_probe[{json.dumps(name)}] || null')
            f = k - sc['new_start_frame'] + 1
            if isinstance(v, list) or (v is None and mk.arg(a, 'kinds')):   # several objects (tokens): one pose each
                n_ = len(mk.arg(a, 'kinds').split(',')); vv = (v or []) + [None] * n_
                ps = [pose_of(x) for x in vv[:n_]]
                vis_ = [q for q in ps if q['z'] < 40] or ps[:1]
                frames.append({'f': f, 'poses': ps, 'pose': {kk: sum(q[kk] for q in vis_) / len(vis_) for kk in ps[0]}}); continue
            if not v or v.get('h', 0) <= 1e-4:
                frames.append({'f': f, 'pose': {'x': 0, 'y': 0, 'z': 50, 'rx': 0, 'ry': 0, 'rz': 0}}); continue
            z = -1.0 / (v['h'] * 2 * th); vh = 2 * (-z) * th; vw = vh * W / H
            frames.append({'f': f, 'pose': {'x': round((v['cx'] - 0.5) * vw, 6), 'y': round((0.5 - v['cy']) * vh, 6), 'z': round(z, 6),
                                            'rx': v.get('rx', 0), 'ry': v.get('ry', 0), 'rz': v.get('rz', 0)}})
            for extra in ('shackle',):   # moving parts of a model (padlock shackle 0 closed .. 1 open)
                if extra in v:
                    frames[-1][extra] = v[extra]
        b.close()
    base = os.path.dirname(os.path.abspath(out))
    job = {'W': W, 'H': H, 'fps': fps, 'fov': fov, 'samples': mk.arg(a, 'samples', 64, int), 'motion_blur': mk.arg(a, 'motion-blur', 0.25, float),
           'hdri': mk.arg(a, 'hdri', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'engine', 'hdri', 'studio_small_08_2k.hdr')),
           'hdri_strength': mk.arg(a, 'hdri-strength', 1.0, float), 'out': os.path.abspath(mk.arg(a, 'out-frames', f'out/render3d/{sid}_{name}/f_####.png')),
           'object': mk.arg(a, 'object', 'icon'), 'frames': frames}
    if job['object'] == 'tokens':
        job['tokens'] = mk.arg(a, 'kinds').split(',')
    if job['object'] == 'icon':
        job['icon'] = {'face': os.path.abspath(mk.arg(a, 'face')), 'depth': 0.16, 'radius': 0.23}
    json.dump(job, open(out, 'w'), indent=1)
    vis = sum(1 for f in frames if f['pose']['z'] < 40)
    print(f'{name} : {len(frames)} images ({vis} visibles), fov {fov}° -> {out}')


if __name__ == '__main__':
    main()
