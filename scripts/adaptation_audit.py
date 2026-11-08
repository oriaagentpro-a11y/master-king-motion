"""Contrôle de STRUCTURE d'une adaptation contre son décalque (règle 105) : rien d'oublié, rien de fantôme, aucun
reste de la référence.

Usage: python3 adaptation_audit.py decalque.mp4 adaptation.mp4 out_dir [--accent 0,254,182] [--fps 25] [--every 6]
Pour chaque image :
- structure = |luminance - flou(15 px)| > 12 (textes, formes, bords ; les fonds dégradés n'en ont pas) ;
- OUBLI   = part de la structure du décalque sans aucune structure de l'adaptation à moins de 9 px ;
- FANTÔME = part de la structure de l'adaptation sans aucune structure du décalque à moins de 25 px ;
- RESTE   = pixels encore dans la teinte d'accent de la RÉFÉRENCE (--accent, RVB) : élément non rebrandé.
Sortie : audit.json (par image + plages signalées) et planche contact (décalque | adaptation | carte) des images signalées
et d'une image toutes les --every. Les seuils sont relatifs : un texte plus long ou plus court reste « normal » ;
une scène vide, un élément resté menthe ou un texte en double ressortent.
"""
import os as _o, sys as _s; _s.path.insert(0, _o.path.dirname(_o.path.abspath(__file__))); import _mkpy  # noqa: E401,E702,F401  (bon Python + PATH)
import sys, json, os
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mkcommon as mk  # noqa: E402


def struct(im):
    g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).astype(np.float32)
    return (np.abs(g - cv2.GaussianBlur(g, (0, 0), 15)) > 12).astype(np.uint8)


def main():
    a = sys.argv
    if len(a) < 4:
        sys.exit(__doc__)
    dec, ada, out = a[1], a[2], a[3]; os.makedirs(out, exist_ok=True)
    acc = np.uint8([[[int(v) for v in mk.arg(a, 'accent', '0,254,182').split(',')][::-1]]])
    hA = int(cv2.cvtColor(acc, cv2.COLOR_BGR2HSV)[0, 0, 0]); every = mk.arg(a, 'every', 6, int)
    cd, ca = cv2.VideoCapture(dec), cv2.VideoCapture(ada); rows = []; keep = {}
    K9, K25 = np.ones((19, 19), np.uint8), np.ones((51, 51), np.uint8)
    f = 0
    while True:
        okd, D = cd.read(); oka, A = ca.read()
        if not (okd and oka):
            break
        sD, sA = struct(D), struct(A)
        nD, nA = int(sD.sum()), int(sA.sum())
        miss = float((sD & (1 - cv2.dilate(sA, K9))).sum() / max(1, nD)) if nD > 300 else 0.0
        ghost = float((sA & (1 - cv2.dilate(sD, K25))).sum() / max(1, nA)) if nA > 300 else 0.0
        hsv = cv2.cvtColor(A, cv2.COLOR_BGR2HSV)
        rest = int(((np.abs(hsv[..., 0].astype(int) - hA) < 7) & (hsv[..., 1] > 120) & (hsv[..., 2] > 110)).sum())
        rows.append({'f': f, 'struct_dec': nD, 'struct_ada': nA, 'oubli': round(miss, 3), 'fantome': round(ghost, 3), 'reste_accent_px': rest})
        flag = miss > 0.45 or ghost > 0.45 or rest > 150 or (nD > 2000 and nA < nD * 0.15)
        if flag or f % every == 0:
            vis = cv2.merge([sD * 255, np.zeros_like(sD), sA * 255])
            keep[f] = (cv2.resize(D, (368, 207)), cv2.resize(A, (368, 207)), cv2.resize(vis, (368, 207)), flag)
        f += 1
    runs = []
    for key, test in (('oubli', lambda r: r['oubli'] > 0.45), ('fantome', lambda r: r['fantome'] > 0.45),
                      ('reste_accent', lambda r: r['reste_accent_px'] > 150), ('scene_vide', lambda r: r['struct_dec'] > 2000 and r['struct_ada'] < r['struct_dec'] * 0.15)):
        cur = None
        for r in rows:
            if test(r):
                cur = [r['f'], r['f']] if cur is None else [cur[0], r['f']]
            elif cur:
                runs.append({'type': key, 'de': cur[0], 'a': cur[1]}); cur = None
        if cur:
            runs.append({'type': key, 'de': cur[0], 'a': cur[1]})
    json.dump({'images': len(rows), 'plages': runs, 'par_image': rows}, open(os.path.join(out, 'audit.json'), 'w'))
    tiles = []
    for fr, (d, ad, v, flag) in sorted(keep.items()):
        row = np.hstack([d, ad, v])
        cv2.putText(row, f'{fr}' + (' !' if flag else ''), (6, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255) if flag else (255, 255, 255), 1)
        tiles.append(row)
    for i in range(0, len(tiles), 30):
        cv2.imwrite(os.path.join(out, f'planche_{i // 30:02d}.jpg'), np.vstack(tiles[i:i + 30]), [cv2.IMWRITE_JPEG_QUALITY, 80])
    print(f'{len(rows)} images ; plages signalées : {len(runs)}')
    for r in runs:
        print(f"  {r['type']:12s} {r['de']}-{r['a']}")


if __name__ == '__main__':
    main()
