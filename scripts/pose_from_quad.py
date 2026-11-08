"""3D pose of a phone (or any flat screen / card) on every frame, from the 4 corners of its screen (solvePnP).

Usage: python3 pose_from_quad.py <quad.json> <ref.mp4> <out.json> [--fov auto|30] [--aspect 0.458] [--screen-h 0.9567]
                                 [--id phone] [--smooth 2] [--poly 2] [--obj-w W --obj-h H] [--frames 353-365,388-401]
- quad.json : track_quad.py output (corners TL, TR, BR, BL of the SCREEN, in reference pixels)
- the screen is a rectangle of known shape: height --screen-h (phone height = 1 world unit, same as mk-phone3d.js)
  and aspect --aspect (width / height of the screen)
- --fov auto : the vertical field of view is searched (6..70 deg) to minimise the reprojection error over all frames
--obj-w/--obj-h : measure another rigid rectangle lying on the screen (a UI card) when the screen corners are out of
frame; its pose = the screen's pose (same plane). --frames keeps only frames where it is at rest. --poly N : one smooth
polynomial per parameter (slow shots: kills the corner jitter of small objects). The two-fold IPPE ambiguity is solved
by temporal continuity.
Writes out.json[id] = {fov, frames: {f: {x, y, z, rx, ry, rz, err_px}}} in mk-phone3d.js camera space (camera at the
origin looking down -z, y up, phone height 1), Euler order YXZ in degrees. The film replays it with
P.setPose(MK.curveAt(pose, t_ref_abs)). Frames where the screen is hidden (phone seen from the back) are simply
missing: measure the silhouette there (track_mask) and keep continuity (rotation through 180 deg).
"""
import os as _o, sys as _s; _s.path.insert(0, _o.path.dirname(_o.path.abspath(__file__))); import _mkpy  # noqa: E401,E702,F401  (bon Python + PATH)
import sys, os, json
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mkcommon as mk  # noqa: E402

C = np.diag([1.0, -1.0, -1.0])  # OpenCV camera (x right, y down, z forward) -> Three.js (x right, y up, z backward)


def euler_yxz(R):
    """R = Ry @ Rx @ Rz (Three.js order 'YXZ') -> degrees (rx, ry, rz)."""
    rx = np.arcsin(-np.clip(R[1, 2], -1, 1))
    if abs(np.cos(rx)) > 1e-6:
        ry = np.arctan2(R[0, 2], R[2, 2]); rz = np.arctan2(R[1, 0], R[1, 1])
    else:
        ry = np.arctan2(-R[2, 0], R[0, 0]); rz = 0.0
    return np.degrees([rx, ry, rz])


def solve(quads, W, H, fov, sw, sh):
    f = (H / 2) / np.tan(np.radians(fov) / 2)
    K = np.array([[f, 0, W / 2], [0, f, H / 2], [0, 0, 1]], float)
    obj = np.array([[-sw / 2, sh / 2, 0], [sw / 2, sh / 2, 0], [sw / 2, -sh / 2, 0], [-sw / 2, -sh / 2, 0]], float)  # TL TR BR BL, y up
    obj_cv = obj * [1, -1, 1]  # OpenCV object frame y down
    out, errs = {}, []
    prev = None
    for fr in sorted(quads):
        q = quads[fr]
        img = np.array(q, float)
        # a small, nearly frontal plane has TWO valid poses (IPPE ambiguity): keep the one closest to the previous frame
        n, rv, tv, re = cv2.solvePnPGeneric(obj_cv, img, K, None, flags=cv2.SOLVEPNP_IPPE)
        if not n:
            continue
        cand = list(zip(rv, tv, re.ravel() if re is not None else [0] * n))
        if prev is not None:
            cand.sort(key=lambda c: np.linalg.norm(cv2.Rodrigues(c[0])[0] - prev))
        else:
            cand.sort(key=lambda c: c[2])
        rvec, tvec = cand[0][0], cand[0][1]; prev = cv2.Rodrigues(rvec)[0]
        proj, _ = cv2.projectPoints(obj_cv, rvec, tvec, K, None)
        e = float(np.sqrt(((proj.reshape(-1, 2) - img) ** 2).sum(1).mean()))
        R, _ = cv2.Rodrigues(rvec)
        # object frame: OpenCV object (y down) -> phone frame (y up): R_obj = R @ diag(1,-1,-1)? object z must point to the viewer
        Rt = C @ R @ np.diag([1.0, -1.0, -1.0])
        t = C @ tvec.reshape(3)
        rx, ry, rz = euler_yxz(Rt)
        out[int(fr)] = {'x': round(float(t[0]), 5), 'y': round(float(t[1]), 5), 'z': round(float(t[2]), 5),
                        'rx': round(float(rx), 3), 'ry': round(float(ry), 3), 'rz': round(float(rz), 3), 'err_px': round(e, 3)}
        errs.append(e)
    return out, (float(np.mean(errs)) if errs else 1e9)


def main():
    a = sys.argv
    if len(a) < 4:
        sys.exit(__doc__)
    J = json.load(open(a[1])); V = mk.probe(a[2]); out = a[3]
    rows = J['rows']; quads = {int(f): r['quad'] for f, r in rows.items()}
    asp = mk.arg(a, 'aspect', 0.458, float); sh = mk.arg(a, 'screen-h', 0.9567, float); sw = sh * asp
    if mk.arg(a, 'obj-w'):  # another rigid rectangle on the screen plane (UI card...): its size in phone units
        sw = mk.arg(a, 'obj-w', None, float); sh = mk.arg(a, 'obj-h', None, float)
    frames_sel = mk.arg(a, 'frames')
    if frames_sel:
        keep = set()
        for part in frames_sel.split(','):
            a0, _, a1 = part.partition('-'); keep |= set(range(int(a0), int(a1 or a0) + 1))
        quads = {f: q for f, q in quads.items() if f in keep}
    fov = mk.arg(a, 'fov', 'auto')
    if fov == 'auto':
        best = min(((solve(quads, V['w'], V['h'], fv, sw, sh)[1], fv) for fv in range(6, 71, 2)))
        fv0 = best[1]
        best = min(((solve(quads, V['w'], V['h'], fv, sw, sh)[1], fv) for fv in np.arange(fv0 - 2, fv0 + 2.01, 0.25)))
        fov = float(best[1])
    else:
        fov = float(fov)
    res, err = solve(quads, V['w'], V['h'], fov, sw, sh)
    poly = mk.arg(a, 'poly', 0, int)
    if poly and len(res) > poly + 2:   # slow shot: one smooth polynomial per parameter over the measured frames
        fr = np.array(sorted(res)); res_s = {}
        for p in ('x', 'y', 'z', 'rx', 'ry', 'rz'):
            c = np.polyfit(fr, [res[f][p] for f in fr], poly)
            for f in fr:
                res_s.setdefault(int(f), {})[p] = round(float(np.polyval(c, f)), 5)
        for f in fr:
            res_s[int(f)]['err_px'] = res[int(f)]['err_px']
        res = res_s
    k = mk.arg(a, 'smooth', 2, int) if not poly else 0
    if k > 0 and len(res) > 2 * k + 1:  # light temporal smoothing (corner jitter), never across gaps
        fr = sorted(res)
        sm = {}
        for i, f in enumerate(fr):
            win = [g for g in fr[max(0, i - k):i + k + 1] if abs(g - f) <= k]
            sm[f] = {p: round(float(np.mean([res[g][p] for g in win])), 5) for p in ('x', 'y', 'z', 'rx', 'ry', 'rz')}
            sm[f]['err_px'] = res[f]['err_px']
        res = sm
    data = json.load(open(out)) if os.path.exists(out) else {}
    eid = mk.arg(a, 'id', 'phone')
    data[eid] = {'id': eid, 'kind': 'pose3d', 'fov': fov, 'fps': V['fps'], 'screen': {'w': sw, 'h': sh}, 'frames': res,
                 'note': 'P.setPose(MK.curveAt(pose, t_ref_abs)) avec la caméra du film au même fov', 'mean_err_px': round(err, 3)}
    mk.save_json(data, out)
    print(f'{eid}: pose 3D sur {len(res)} images, fov {fov:.2f}°, erreur de reprojection moyenne {err:.2f} px -> {out}')


if __name__ == '__main__':
    main()
