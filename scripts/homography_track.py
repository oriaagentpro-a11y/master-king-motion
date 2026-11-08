"""Mouvement EXACT d'un écran / d'une surface plane, image par image : homographie chaînée (règles 91, 93).

Usage: python3 homography_track.py ref.mp4 f0 f1 key out.json [--quad x,y,x,y,x,y,x,y] [--mask x,y,w,h] [--min 25]
- key : image de référence ; le « canevas » est soit le quadrilatère --quad (4 coins de l'écran dans cette image, sens
  horaire depuis le haut-gauche), soit l'image entière.
- Pour chaque image, des points ORB sont appariés avec l'image précédente (RANSAC), les homographies sont chaînées
  depuis key dans les deux sens, puis RE-RECALÉES directement sur key quand c'est possible (moins de dérive).
- Sortie : {"key": k, "quad": [[x,y]x4], "W": w, "H": h, "frames": {f: [[h11..h33]] 3x3 canevas->image | null},
            "corners": {f: [[x,y]x4]}}  (coins du canevas dans chaque image = pour CSS matrix3d / RM.quadMatrix3d)
Le film pose son contenu (le décalque recréé en code, puis le contenu de l'utilisateur) sur ces coins : le mouvement de
caméra, la perspective et la parallaxe de l'écran sont ceux de la référence, à la fraction de pixel.
Images floues (fouets) : peu de points -> null ; le film interpole les coins entre les images voisines.
"""
import sys, json
import numpy as np
import cv2

sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import mkcommon as mk  # noqa: E402


def main():
    a = sys.argv
    if len(a) < 6:
        sys.exit(__doc__)
    src, f0, f1, key, out = a[1], int(a[2]), int(a[3]), int(a[4]), a[5]
    cap = cv2.VideoCapture(src); cap.set(cv2.CAP_PROP_POS_FRAMES, f0)
    G = {}
    for f in range(f0, f1 + 1):
        ok, im = cap.read()
        if not ok:
            break
        G[f] = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    H_, W_ = G[key].shape
    q = [float(v) for v in mk.arg(a, 'quad', '').split(',')] if mk.arg(a, 'quad') else [0, 0, W_, 0, W_, H_, 0, H_]
    quad = np.array(q, np.float32).reshape(4, 2)
    cw = float(np.linalg.norm(quad[1] - quad[0])); ch = float(np.linalg.norm(quad[3] - quad[0]))
    canvas = np.array([[0, 0], [cw, 0], [cw, ch], [0, ch]], np.float32)
    H0 = cv2.getPerspectiveTransform(canvas, quad)          # canevas -> image key
    orb = cv2.ORB_create(4000, fastThreshold=7)
    mask = None
    if mk.arg(a, 'mask'):
        x, y, w, h = map(int, mk.arg(a, 'mask').split(',')); mask = np.zeros_like(G[key]); mask[y:y + h, x:x + w] = 255
    feats = {f: orb.detectAndCompute(g, mask) for f, g in G.items()}
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True); minm = mk.arg(a, 'min', 25, int)

    def pair(fa, fb):   # homographie image fa -> image fb
        ka, da = feats[fa]; kb, db = feats[fb]
        if da is None or db is None or len(ka) < 8 or len(kb) < 8:
            return None
        m = sorted(bf.match(da, db), key=lambda x: x.distance)[:800]
        if len(m) < minm:
            return None
        pa = np.float32([ka[x.queryIdx].pt for x in m]); pb = np.float32([kb[x.trainIdx].pt for x in m])
        Hm, inl = cv2.findHomography(pa, pb, cv2.RANSAC, 2.0)
        if Hm is None or inl.sum() < minm:
            return None
        return Hm
    res = {key: H0}
    for direction in (1, -1):
        prev = key; Hc = H0
        rng = range(key + 1, f1 + 1) if direction > 0 else range(key - 1, f0 - 1, -1)
        for f in rng:
            Hd = pair(key, f)                     # direct vers key (pas de dérive) si assez de points communs
            if Hd is not None:
                Hc = Hd @ H0
            else:
                Hp = pair(prev, f)
                if Hp is None:
                    res[f] = None; continue
                Hc = Hp @ Hc
            res[f] = Hc; prev = f
    corners = {}
    for f, Hm in res.items():
        if Hm is None:
            corners[f] = None; continue
        c = cv2.perspectiveTransform(canvas.reshape(-1, 1, 2), Hm).reshape(-1, 2)
        corners[f] = [[round(float(x), 2), round(float(y), 2)] for x, y in c]
    json.dump({'key': key, 'quad': quad.tolist(), 'W': cw, 'H': ch,
               'frames': {str(f): (None if Hm is None else (Hm / Hm[2, 2]).tolist()) for f, Hm in res.items()},
               'corners': {str(f): c for f, c in corners.items()}}, open(out, 'w'))
    ok_ = sum(1 for v in res.values() if v is not None)
    print(f'{ok_}/{len(res)} images suivies -> {out}')


if __name__ == '__main__':
    main()
