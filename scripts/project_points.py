"""Project points attached to a 3D object of a Blender job onto the screen, for every frame, so that 2D overlays
(callouts, labels, connector lines) aim EXACTLY at the 3D render (rule 76).

Usage: python3 project_points.py job.json out.js --var P3PTS --points name:x,y,z[:card=i] ...
- point coordinates are in the OBJECT's local space (phone: 1 unit = phone height, origin at its centre, +Z = screen
  side). `:card=i` adds card i's lift (frames[k].cards[i].z) and its local y (job.cards[i].y) - x,y,z are then
  relative to the card's centre (e.g. its left edge: -w/2,0,0).
- the camera is the job's: origin, looking -Z, vertical fov, rotation mode ZXY (R = Ry.Rx.Rz) like render_job.py.
Writes `window.<var> = {W, H, first, frames: {k: {name: [x_px, y_px], ...}}}` (k = job frame) for the film recipe.
"""
import os as _o, sys as _s; _s.path.insert(0, _o.path.dirname(_o.path.abspath(__file__))); import _mkpy  # noqa: E401,E702,F401  (bon Python + PATH)
import sys, os, json, math
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mkcommon as mk  # noqa: E402

D_PHONE = 8.25 / 147.0


def rot(rx, ry, rz):
    rx, ry, rz = map(math.radians, (rx, ry, rz))
    Rx = np.array([[1, 0, 0], [0, math.cos(rx), -math.sin(rx)], [0, math.sin(rx), math.cos(rx)]])
    Ry = np.array([[math.cos(ry), 0, math.sin(ry)], [0, 1, 0], [-math.sin(ry), 0, math.cos(ry)]])
    Rz = np.array([[math.cos(rz), -math.sin(rz), 0], [math.sin(rz), math.cos(rz), 0], [0, 0, 1]])
    return Ry @ Rx @ Rz


def main():
    a = sys.argv
    if len(a) < 4:
        sys.exit(__doc__)
    J = json.load(open(a[1])); out = a[2]; var = mk.arg(a, 'var', 'PTS')
    W, H = J['W'], J['H']; th = math.tan(math.radians(J['fov']) / 2)
    specs = []
    i = a.index('--points') + 1
    while i < len(a) and not a[i].startswith('--'):
        parts = a[i].split(':'); nm = parts[0]; xyz = [float(v) for v in parts[1].split(',')]
        card = int(parts[2].split('=')[1]) if len(parts) > 2 and parts[2].startswith('card=') else None
        specs.append((nm, np.array(xyz), card)); i += 1
    res = {}
    for fr in J['frames']:
        p = fr['pose']; R = rot(p.get('rx', 0), p.get('ry', 0), p.get('rz', 0)); T = np.array([p['x'], p['y'], p['z']])
        pts = {}
        for nm, xyz, card in specs:
            loc = xyz.copy()
            if card is not None:
                c = J['cards'][card]; cz = fr.get('cards', [{}] * (card + 1))[card].get('z', 0)
                loc = loc + np.array([0, c['y'], D_PHONE / 2 + 0.0004 + cz])
            w = T + R @ loc
            if w[2] >= -1e-6:
                continue
            sx = W / 2 + (w[0] / -w[2]) / th * H / 2; sy = H / 2 - (w[1] / -w[2]) / th * H / 2
            pts[nm] = [round(float(sx), 1), round(float(sy), 1)]
        res[fr['f']] = pts
    open(out, 'w').write(f'window.{var} = ' + json.dumps({'W': W, 'H': H, 'frames': res}) + ';\n')
    print(f'{len(res)} images, {len(specs)} points -> {out}')


if __name__ == '__main__':
    main()
