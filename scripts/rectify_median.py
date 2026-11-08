"""Texture propre d'un écran / d'une surface suivie : médiane temporelle des images redressées (règles 93, 95).

Usage: python3 rectify_median.py ref.mp4 track.json out.png [--frames a-b] [--step 1] [--occ occ.json] [--scale 2] [--drop-light 150]
- track.json : sortie de homography_track.py (W, H, corners par image).
- occ.json   : {"<frame>": [[[x,y]x4], ...]} quadrilatères (en pixels de la référence) qui MASQUENT l'écran à cette image
               (étiquette posée dessus, curseur, pièce...) : ces pixels sont exclus de la médiane.
- --drop-light T : exclut aussi les pixels clairs (min BGR > T, dilatés) = le TEXTE posé sur une face (étiquette,
               bouton) ; on obtient la face seule, le texte est rejoué en vraie police par-dessus.
- chaque image est redressée sur le canevas (W*scale x H*scale) ; la médiane par pixel, sur les seules images où il est
  visible, enlève le bruit de compression, les occultations et le flou passager.
Sortie : une image de travail (PNG) qu'on passe à vectorize_image.py --image ; elle n'entre JAMAIS telle quelle dans le
film (règle 93) : c'est la planche de mesure qui donne au vecteur ses couleurs et ses formes exactes.
"""
import os as _o, sys as _s; _s.path.insert(0, _o.path.dirname(_o.path.abspath(__file__))); import _mkpy  # noqa: E401,E702,F401  (bon Python + PATH)
import sys, json
import numpy as np
import cv2

sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import mkcommon as mk  # noqa: E402


def main():
    a = sys.argv
    if len(a) < 4:
        sys.exit(__doc__)
    src, tr, out = a[1], json.load(open(a[2])), a[3]
    sc = mk.arg(a, 'scale', 2.0, float); step = mk.arg(a, 'step', 1, int)
    W, H = int(round(tr['W'] * sc)), int(round(tr['H'] * sc))
    C = {int(k): v for k, v in tr['corners'].items() if v}
    fr = sorted(C)
    if mk.arg(a, 'frames'):
        f0, f1 = map(int, mk.arg(a, 'frames').split('-')); fr = [f for f in fr if f0 <= f <= f1]
    fr = fr[::step]
    occ = json.load(open(mk.arg(a, 'occ'))) if mk.arg(a, 'occ') else {}
    cap = cv2.VideoCapture(src); cap.set(cv2.CAP_PROP_POS_FRAMES, fr[0]); cur = fr[0]
    stack, masks = [], []
    dst = np.float32([[0, 0], [W, 0], [W, H], [0, H]])
    for f in fr:
        while cur <= f:
            ok, im = cap.read(); cur += 1
        M = cv2.getPerspectiveTransform(np.float32(C[f]), dst)
        r = cv2.warpPerspective(im, M, (W, H), flags=cv2.INTER_CUBIC)
        m = np.ones(im.shape[:2], np.uint8) * 255
        for q in occ.get(str(f), []):
            cv2.fillPoly(m, [np.array(q, np.int32)], 0)
        m = cv2.erode(m, np.ones((5, 5), np.uint8))
        if mk.arg(a, 'drop-light'):
            lt = (im.min(2) > mk.arg(a, 'drop-light', 150, float)).astype(np.uint8)
            m[cv2.dilate(lt, np.ones((7, 7), np.uint8)) > 0] = 0
        mr = cv2.warpPerspective(m, M, (W, H), flags=cv2.INTER_NEAREST, borderValue=0)
        stack.append(r); masks.append(mr > 0)
    S = np.stack(stack).astype(np.float32); K = np.stack(masks)
    S[~K] = np.nan
    med = np.nanmedian(S, axis=0)
    hole = np.isnan(med[..., 0])
    med = np.nan_to_num(med).astype(np.uint8)
    if hole.any():
        med = cv2.inpaint(med, hole.astype(np.uint8), 5, cv2.INPAINT_TELEA)
    cv2.imwrite(out, med)
    print(f'{len(fr)} images -> {out} ({W}x{H}), trous comblés {hole.mean():.1%}')


if __name__ == '__main__':
    main()
