"""Match-move: refine a phone's 3D pose on every frame by snapping its projected OUTLINES onto the frame's edges.

Use it when the screen corners are not all visible (close-up, phone cropped by the frame / a panel) or when a corner
based pose fails its check (rule 20c). The 3D outlines of the phone (body silhouette, screen border, island) are
projected with the camera, and the 6 pose parameters are optimised so that the projected points fall on the image
edges (mean distance-transform of the Canny edges), starting from the previous frame.

Usage: python3 pose_refine_edges.py <ref.mp4> <f0> <f1> <out.json> --fov 20 --init x,y,z,rx,ry,rz [--id phone]
                                    [--roi x,y,w,h] [--step 1] [--fov-search 10,40] [--debug dir] [--poly 2]
--anchor u,v,w : landmark init instead of --init — pixel centre of the camera island and its apparent width (read on a
gridded zoom of the first frame, noted as « œil »); rotations and focal (--fovs list) are searched on a grid.
--init: starting pose for f0 (camera space of mk-phone3d.js, phone 1 unit tall, degrees, Euler YXZ)
--fov-search a,b: also search the vertical fov on the first frames (closest fit)
--roi: only edges inside it count (e.g. the inset panel of a shot) ; --debug writes overlays every 5 frames.
Geometry = blender/phone_build.py proportions (screen inset 2.05 mm, corner 10.6 mm, island 19 x 5.6 mm).
"""
import os as _o, sys as _s; _s.path.insert(0, _o.path.dirname(_o.path.abspath(__file__))); import _mkpy  # noqa: E401,E702,F401  (bon Python + PATH)
import sys, os, json
import numpy as np
import cv2
from scipy.optimize import minimize

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mkcommon as mk  # noqa: E402

MM = 1 / 147.0
W_, H_, D_ = 71.5 * MM, 1.0, 8.25 * MM


def rr_outline(w, h, r, n=24, z=0.0, dy=0.0):
    pts = []
    for cx, cy, a0 in ((w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90), (-w / 2 + r, -h / 2 + r, 180), (w / 2 - r, -h / 2 + r, 270)):
        for k in range(n):
            t = np.radians(a0 + 90 * k / n); pts.append((cx + r * np.cos(t), cy + dy + r * np.sin(t), z))
    # densify straight sides
    P = np.array(pts); out = []
    for i in range(len(P)):
        a, b = P[i], P[(i + 1) % len(P)]; m = max(1, int(np.linalg.norm(b - a) / (2 * MM)))
        out += [a + (b - a) * j / m for j in range(m)]
    return np.array(out)


BEZ = 2.05 * MM
OUT = {
    'body': rr_outline(W_, H_, 10.6 * MM, z=D_ / 2 - 0.4 * MM),
    'screen': rr_outline(W_ - 2 * BEZ, H_ - 2 * BEZ, 8.7 * MM, z=D_ / 2 + 0.2 * MM),
    'island': rr_outline(19 * MM, 5.6 * MM, 2.8 * MM, n=10, z=D_ / 2 + 0.2 * MM, dy=H_ / 2 - BEZ - 5.2 * MM),
}
PTS = np.vstack([OUT['body'], OUT['screen'], OUT['island']])
WGT = np.concatenate([np.full(len(OUT['body']), 1.0), np.full(len(OUT['screen']), 1.0), np.full(len(OUT['island']), 2.0)])


def rot(rx, ry, rz):
    rx, ry, rz = np.radians([rx, ry, rz])
    Rx = np.array([[1, 0, 0], [0, np.cos(rx), -np.sin(rx)], [0, np.sin(rx), np.cos(rx)]])
    Ry = np.array([[np.cos(ry), 0, np.sin(ry)], [0, 1, 0], [-np.sin(ry), 0, np.cos(ry)]])
    Rz = np.array([[np.cos(rz), -np.sin(rz), 0], [np.sin(rz), np.cos(rz), 0], [0, 0, 1]])
    return Ry @ Rx @ Rz


def project(p, K):
    R = rot(*p[3:]); P = (R @ PTS.T).T + p[:3]
    nrm = R @ np.array([0, 0, 1.0])                       # front faces the camera only if normal . view < 0
    uvw = (K @ (P * [1, -1, -1]).T).T
    uv = uvw[:, :2] / np.maximum(uvw[:, 2:3], 1e-6)
    return uv, nrm, P


def cost(p, K, dt, mask, W, H):
    uv, nrm, P = project(p, K)
    if P[:, 2].max() > -0.05:
        return 1e6
    ok = (uv[:, 0] >= 1) & (uv[:, 0] < W - 1) & (uv[:, 1] >= 1) & (uv[:, 1] < H - 1)
    if ok.sum() < 30:
        return 1e5
    u = uv[ok].astype(int); inside = mask[u[:, 1], u[:, 0]] > 0
    if inside.sum() < 30:
        return 1e5
    d = dt[u[inside, 1], u[inside, 0]]
    w = WGT[ok][inside]
    return float(np.sum(np.minimum(d, 12) * w) / np.sum(w)) + 4.0 * (1 - inside.mean())


def main():
    a = sys.argv
    if len(a) < 5:
        sys.exit(__doc__)
    video, f0, f1, out = a[1], int(a[2]), int(a[3]), a[4]
    V = mk.probe(video); W, H = V['w'], V['h']
    fov = mk.arg(a, 'fov', 20, float); step = mk.arg(a, 'step', 1, int)
    p = np.array([float(v) for v in (mk.arg(a, 'init') or '0,0,-3,0,0,0').split(',')])
    roi = list(map(int, mk.arg(a, 'roi', f'0,0,{W},{H}').split(','))); dbg = mk.arg(a, 'debug')
    if dbg:
        os.makedirs(dbg, exist_ok=True)
    cap = cv2.VideoCapture(video)

    def frame_maps(f):
        cap.set(cv2.CAP_PROP_POS_FRAMES, f); ok, im = cap.read()
        g = cv2.GaussianBlur(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY), (3, 3), 0)
        e = cv2.Canny(g, 30, 90)
        dt = cv2.distanceTransform((255 - e).astype(np.uint8), cv2.DIST_L2, 3)
        mask = np.zeros((H, W), np.uint8); x, y, w, h = roi; mask[y:y + h, x:x + w] = 1
        return im, dt, mask

    def Kof(fv):
        fpx = (H / 2) / np.tan(np.radians(fv) / 2); return np.array([[fpx, 0, W / 2], [0, fpx, H / 2], [0, 0, 1.0]])

    def fit(p0, dt, mask, K):
        best = None
        for scale in (1.0, 0.5):
            r = minimize(cost, p0, args=(K, dt, mask, W, H), method='Nelder-Mead',
                         options={'xatol': 1e-4, 'fatol': 1e-3, 'maxiter': 3000, 'initial_simplex': None})
            if best is None or r.fun < best.fun:
                best = r
            p0 = best.x
        return best
    anc = mk.arg(a, 'anchor')
    if anc:
        # init by search: rotations on a grid, position from the island anchor (pixel centre + apparent width),
        # several focal lengths; keep the lowest edge cost, then refine (match-move "landmark" init)
        au, av, aw = map(float, anc.split(','))
        im, dt, mask = frame_maps(f0); best = None
        fovs = [float(v) for v in (mk.arg(a, 'fovs') or '8.5,12,16,20,25,30').split(',')]
        isl_c = np.array([0, H_ / 2 - BEZ - 5.2 * MM, D_ / 2])
        for fv in fovs:
            K_ = Kof(fv); fpx = K_[0, 0]
            for rx in range(-45, 6, 5):
                for ry in range(-50, 11, 5):
                    for rz in range(-25, 11, 5):
                        R = rot(rx, ry, rz)
                        wvec = R @ np.array([19 * MM, 0, 0]); wproj = np.hypot(wvec[0], wvec[1])
                        z = -fpx * wproj / max(aw, 1)
                        c = R @ isl_c
                        X = (au - W / 2) / fpx * (-z) - c[0]; Y = -(av - H / 2) / fpx * (-z) - c[1]; Z = z - c[2]
                        p_ = np.array([X, Y, Z, rx, ry, rz], float); cst = cost(p_, K_, dt, mask, W, H)
                        if best is None or cst < best[0]:
                            best = (cst, fv, p_)
        _, fov, p = best
        r = fit(p, dt, mask, Kof(fov)); p = r.x
        print(f'ancre : fov {fov}°, coût initial {best[0]:.3f} -> affiné {r.fun:.3f}')
    fs = mk.arg(a, 'fov-search')
    if fs:
        lo, hi = map(float, fs.split(','))
        im, dt, mask = frame_maps(f0); res = []
        for fv in np.arange(lo, hi + 0.01, 2.0):
            # keep the apparent size: scale the distance with the focal length
            p_ = p.copy(); p_[2] = p[2] * np.tan(np.radians(fov) / 2) / np.tan(np.radians(fv) / 2)
            p_[0] *= p_[2] / p[2]; p_[1] *= p_[2] / p[2]
            r = fit(p_, dt, mask, Kof(fv)); res.append((r.fun, fv, r.x))
        res.sort(key=lambda t: t[0]); _, fov, p = res[0]
        print(f'fov retenu {fov:.1f}° (coût {res[0][0]:.3f})')
    K = Kof(fov); rows = {}
    for f in range(f0, f1 + 1, step):
        im, dt, mask = frame_maps(f)
        r = fit(p, dt, mask, K); p = r.x
        rows[f] = {k: round(float(v), 5) for k, v in zip(('x', 'y', 'z', 'rx', 'ry', 'rz'), p)}; rows[f]['cost_px'] = round(float(r.fun), 3)
        if dbg and (f - f0) % 5 == 0:
            uv, _, _ = project(p, K); o = im.copy()
            for q in uv.astype(int):
                if 0 <= q[0] < W and 0 <= q[1] < H:
                    o[q[1], q[0]] = (0, 0, 255)
            cv2.imwrite(os.path.join(dbg, f'f{f:05d}.png'), o)
    poly = mk.arg(a, 'poly', 0, int)
    if poly and len(rows) > poly + 2:
        fr = np.array(sorted(rows))
        for k in ('x', 'y', 'z', 'rx', 'ry', 'rz'):
            c = np.polyfit(fr, [rows[f][k] for f in fr], poly)
            for f in fr:
                rows[int(f)][k] = round(float(np.polyval(c, f)), 5)
    data = json.load(open(out)) if os.path.exists(out) else {}
    eid = mk.arg(a, 'id', 'phone')
    data[eid] = {'id': eid, 'kind': 'pose3d', 'method': 'contours (match-move)', 'fov': fov, 'fps': V['fps'], 'frames': rows,
                 'mean_cost_px': round(float(np.mean([r['cost_px'] for r in rows.values()])), 3)}
    mk.save_json(data, out)
    print(f"{eid}: pose sur {len(rows)} images, fov {fov:.1f}°, écart moyen aux contours {data[eid]['mean_cost_px']} px -> {out}")


if __name__ == '__main__':
    main()
