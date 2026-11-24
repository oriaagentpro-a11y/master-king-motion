"""Pose 3D d'une CARTE rigide (notification, carte de solde, étiquette) à partir de ses 4 coins suivis (règle 132).

Usage: python3 card_pose.py corners.json out.json --fov 50 [--id carte] [--aspect auto|2.8] [--width 0.42]
                            [--frames a-b] [--W 720 --H 1280] [--smooth 7]
- corners.json : sortie de homography_track.py / homography_refine.py ({"corners": {f: [[x,y]x4]}}) ou de
  track_quad.py ({"rows": {f: {"quad": ...}}}). Coins TL, TR, BR, BL de la FACE de la carte (sans ombre ni tranche).
- --fov : focale verticale de la prise (celle du téléphone mesuré par pose_refine_edges.py, même caméra).
- --aspect auto : le rapport largeur / hauteur réel de la carte est cherché (1,5 à 6) pour minimiser l'erreur de
  reprojection sur toutes les images : un quadrilatère suivi n'est presque jamais un vrai rectangle en perspective
  (coins bruités, ombre prise dans le masque) ; la carte, elle, l'est.
- --width : largeur de la carte en unités du film 3D (téléphone = 1 de haut) ; fixe l'échelle profondeur / taille.
Sortie : {id: {fov, aspect, width, height, frames: {f: {x,y,z,rx,ry,rz, err_px}}, clean: {f: [[x,y]x4]}}}
  frames = pose lissée (Savitzky-Golay, règle 110) dans l'espace caméra de mk-phone3d.js (même convention que
  pose_from_quad.py) ; clean = les 4 coins REPROJETÉS d'un vrai rectangle : à utiliser à la place des coins bruts.
Cas réel (Monniz, réf. A f49-62) : la notification suivie avait un côté gauche de 98 px et un côté droit de 171 px
(l'ombre de la carte prise dans le quadrilatère) : posée telle quelle, la face était déformée en trapèze. Rectangle
rigide + pose 3D + tranche rendue en vrai 3D = carte « bien posée » comme sur la référence.
"""
import os as _o, sys as _s; _s.path.insert(0, _o.path.dirname(_o.path.abspath(__file__))); import _mkpy  # noqa: E401,E702,F401
import sys, os, json
import numpy as np
import cv2
from scipy.signal import savgol_filter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mkcommon as mk  # noqa: E402
from pose_from_quad import euler_yxz, C  # noqa: E402


def load(path):
    J = json.load(open(path, encoding='utf-8'))
    if 'corners' in J:
        return {int(f): np.array(q, float) for f, q in J['corners'].items() if q}
    rows = J.get('rows', J)
    return {int(f): np.array(r['quad'], float) for f, r in rows.items() if isinstance(r, dict) and r.get('quad')}


def K(W, H, fov):
    f = (H / 2) / np.tan(np.radians(fov) / 2); return np.array([[f, 0, W / 2], [0, f, H / 2], [0, 0, 1]], float)


def solve(quads, Km, w, h):
    obj = np.array([[-w / 2, -h / 2, 0], [w / 2, -h / 2, 0], [w / 2, h / 2, 0], [-w / 2, h / 2, 0]], float)  # y vers le bas (OpenCV)
    out, prev, errs = {}, None, []
    for f in sorted(quads):
        n, rv, tv, _ = cv2.solvePnPGeneric(obj, quads[f], Km, None, flags=cv2.SOLVEPNP_IPPE)
        if not n:
            continue
        cand = list(zip(rv, tv))
        if prev is not None:   # ambiguïté IPPE : continuité temporelle
            cand.sort(key=lambda c: np.linalg.norm(cv2.Rodrigues(c[0])[0] - prev))
        else:
            cand.sort(key=lambda c: -cv2.Rodrigues(c[0])[0][2, 2])
        r, t = cand[0]; prev = cv2.Rodrigues(r)[0]
        p, _ = cv2.projectPoints(obj, r, t, Km, None); e = float(np.sqrt(((p.reshape(-1, 2) - quads[f]) ** 2).sum(1).mean()))
        out[f] = (r.ravel(), t.ravel(), e); errs.append(e)
    return out, float(np.mean(errs)) if errs else 1e9, obj


def rot(rx, ry, rz):   # Euler YXZ (degrés), convention mk-phone3d.js
    rx, ry, rz = np.radians([rx, ry, rz])
    Rx = np.array([[1, 0, 0], [0, np.cos(rx), -np.sin(rx)], [0, np.sin(rx), np.cos(rx)]])
    Ry = np.array([[np.cos(ry), 0, np.sin(ry)], [0, 1, 0], [-np.sin(ry), 0, np.cos(ry)]])
    Rz = np.array([[np.cos(rz), -np.sin(rz), 0], [np.sin(rz), np.cos(rz), 0], [0, 0, 1]])
    return Ry @ Rx @ Rz


def parent_mode(a, quads, out, W, H):
    """--parent poses.json:id : la carte est résolue DANS le repère du téléphone mesuré (décalage dans le plan de l'écran,
    soulèvement, petite inclinaison tirée vers 0). Évite la pose « valide mais absurde » d'un rectangle presque de face
    (ambiguïté : carte tournée de 52° et collée à la caméra, cas Monniz f49-58)."""
    from scipy.optimize import least_squares
    pj, pid = mk.arg(a, 'parent').rsplit(':', 1)
    PP = json.load(open(pj, encoding='utf-8'))[pid]; fov = PP['fov']
    fpx = (H / 2) / np.tan(np.radians(fov) / 2)
    pf = {int(f): v for f, v in PP['frames'].items()}
    width = mk.arg(a, 'width', 0.42, float); reg = mk.arg(a, 'reg', 1.5, float)

    def phone_at(f):
        ks = sorted(pf); f = min(max(f, ks[0]), ks[-1]); i = np.searchsorted(ks, f)
        if ks[i] == f: return pf[f]
        k0, k1 = ks[i - 1], ks[i]; p = (f - k0) / (k1 - k0); return {k: pf[k0][k] + (pf[k1][k] - pf[k0][k]) * p for k in pf[k0]}

    def proj(par, ph, w, h):
        dx, dy, dz, drx, dry, drz = par
        Rp = rot(ph['rx'], ph['ry'], ph['rz']); Rc = Rp @ rot(drx, dry, drz)
        c = np.array([ph['x'], ph['y'], ph['z']]) + Rp @ np.array([dx, dy, dz])
        loc = np.array([[-w / 2, h / 2, 0], [w / 2, h / 2, 0], [w / 2, -h / 2, 0], [-w / 2, -h / 2, 0]])
        P = (Rc @ loc.T).T + c
        return np.column_stack([W / 2 + fpx * P[:, 0] / -P[:, 2], H / 2 - fpx * P[:, 1] / -P[:, 2]])

    def run(h):
        res, prev, errs = {}, np.array([0, 0, 0.02, 0, 0, 0.0]), []
        for f in sorted(quads):
            ph = phone_at(f)
            fun = lambda p: np.concatenate([(proj(p, ph, width, h) - quads[f]).ravel(), reg * np.array(p[3:]) / 3.0])
            r = least_squares(fun, prev, x_scale=[0.05, 0.05, 0.05, 3, 3, 3]); prev = r.x
            e = float(np.sqrt(((proj(r.x, ph, width, h) - quads[f]) ** 2).sum(1).mean())); res[f] = (r.x, ph); errs.append(e)
        return res, float(np.mean(errs))

    asp = mk.arg(a, 'aspect', 'auto')
    if asp == 'auto':
        asp = min((run(width / r)[1], r) for r in np.arange(2.0, 7.01, 0.25))[1]
    asp = float(asp); h = width / asp; res, err = run(h)
    fs = sorted(res); X = np.array([res[f][0] for f in fs]); k = mk.arg(a, 'smooth', 7, int)
    if len(fs) >= k >= 5:
        X = savgol_filter(X, k, 2, axis=0)
    rel, clean = {}, {}
    for i, f in enumerate(fs):
        rel[f] = {n: round(float(v), 5) for n, v in zip(('dx', 'dy', 'dz', 'drx', 'dry', 'drz'), X[i])}
        q = proj(X[i], res[f][1], width, h); clean[f] = q.round(2).tolist()
        rel[f]['err_px'] = round(float(np.sqrt(((q - quads[f]) ** 2).sum(1).mean())), 2)
    data = json.load(open(out, encoding='utf-8')) if os.path.exists(out) else {}
    cid = mk.arg(a, 'id', 'carte')
    data[cid] = {'parent': pid, 'fov': fov, 'aspect': round(asp, 3), 'width': width, 'height': round(h, 5), 'relative': rel, 'clean': clean,
                 'mean_err_px': round(float(np.mean([v['err_px'] for v in rel.values()])), 2)}
    mk.save_json(data, out)
    print(f"{cid} (dans {pid}): {len(rel)} images, rapport {asp:.2f}, écart moyen {data[cid]['mean_err_px']} px -> {out}")


def main():
    a = sys.argv
    if len(a) < 3:
        sys.exit(__doc__)
    quads = load(a[1]); out = a[2]
    fr = mk.arg(a, 'frames')
    if fr:
        f0, f1 = map(int, fr.split('-')); quads = {f: q for f, q in quads.items() if f0 <= f <= f1}
    W, H = mk.arg(a, 'W', 720, float), mk.arg(a, 'H', 1280, float); fov = mk.arg(a, 'fov', 45, float)
    if mk.arg(a, 'parent'):
        return parent_mode(a, quads, out, W, H)
    Km = K(W, H, fov); width = mk.arg(a, 'width', 0.42, float); asp = mk.arg(a, 'aspect', 'auto')
    if asp == 'auto':
        best = min((solve(quads, Km, width, width / r)[1], r) for r in np.arange(1.5, 6.01, 0.05)); asp = float(best[1])
    else:
        asp = float(asp)
    h = width / asp
    sol, err, obj = solve(quads, Km, width, h)
    fs = sorted(sol); R = np.array([sol[f][0] for f in fs]); T = np.array([sol[f][1] for f in fs])
    k = mk.arg(a, 'smooth', 7, int)
    if len(fs) >= k and k >= 5:
        R = savgol_filter(R, k, 2, axis=0); T = savgol_filter(T, k, 2, axis=0)
    frames, clean = {}, {}
    for i, f in enumerate(fs):
        Rm = cv2.Rodrigues(R[i])[0]; p, _ = cv2.projectPoints(obj, R[i], T[i], Km, None); q = p.reshape(-1, 2)
        clean[f] = q.round(2).tolist()
        Rt = C @ Rm @ np.diag([1.0, -1.0, -1.0]); t = C @ T[i]
        rx, ry, rz = euler_yxz(Rt)
        frames[f] = {'x': round(float(t[0]), 5), 'y': round(float(t[1]), 5), 'z': round(float(t[2]), 5),
                     'rx': round(float(rx), 3), 'ry': round(float(ry), 3), 'rz': round(float(rz), 3),
                     'err_px': round(float(np.sqrt(((q - quads[f]) ** 2).sum(1).mean())), 2)}
    data = json.load(open(out, encoding='utf-8')) if os.path.exists(out) else {}
    cid = mk.arg(a, 'id', 'carte')
    data[cid] = {'fov': fov, 'aspect': round(asp, 3), 'width': width, 'height': round(h, 5), 'frames': frames, 'clean': clean,
                 'mean_err_px': round(float(np.mean([v['err_px'] for v in frames.values()])), 2)}
    mk.save_json(data, out)
    print(f"{cid}: {len(frames)} images, rapport {asp:.2f}, écart moyen (rectangle rigide lissé vs coins suivis) {data[cid]['mean_err_px']} px -> {out}")


if __name__ == '__main__':
    main()
