"""Render a psd_rebuild.py page and compare it with the PSD's composite.png, layer by layer (rule 84).

Usage: python3 psd_compare.py out.html analysis/psd report.png [--json report.json]
- screenshots #poster (Playwright, scale 1), resizes composite.png to the same size;
- masks the boxes of the skipped layers (data-skip) on both images (the logo removed on purpose is not an error);
- global mean abs error (0-255) and, for every TEXT layer, the ink box error: |dx|, |dy| of the box edges and the
  size ratio, measured on the difference inside the layer box -> fix size / origin until each text is under 1 px.
Writes report.png: composite | rebuild | x4 amplified difference.
"""
import os as _o, sys as _s; _s.path.insert(0, _o.path.dirname(_o.path.abspath(__file__))); import _mkpy  # noqa: E401,E702,F401  (bon Python + PATH)
import sys, os, json
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mkcommon as mk  # noqa: E402


def ink_box(im, box, bg_tol=40):
    """Box of bright (text) pixels inside box on a dark poster: pixels much brighter than the box's median."""
    x0, y0, x1, y1 = box; c = im[y0:y1, x0:x1].astype(np.float32).mean(2)
    m = c > np.median(c) + bg_tol
    ys, xs = np.where(m)
    if len(xs) < 5:
        return None
    return [x0 + xs.min(), y0 + ys.min(), x0 + xs.max(), y0 + ys.max()]


def main():
    a = sys.argv
    if len(a) < 4:
        sys.exit(__doc__)
    page, src, out = os.path.abspath(a[1]), a[2], a[3]
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = mk.rmcommon.launch(p); pg = b.new_page(viewport={'width': 4000, 'height': 6000})
        pg.goto('file://' + page); pg.wait_for_timeout(800); pg.evaluate('document.fonts.ready')
        info = pg.evaluate("""() => { const P = document.getElementById('poster');
            return {skip: P.dataset.skip, scale: +P.dataset.scale} }""")
        pg.locator('#poster').screenshot(path=out + '.rebuild.png'); b.close()
    R = np.array(Image.open(out + '.rebuild.png').convert('RGB')).astype(np.int16)
    h, w = R.shape[:2]
    C = np.array(Image.open(os.path.join(src, 'composite.png')).convert('RGB').resize((w, h), Image.LANCZOS)).astype(np.int16)
    D = json.load(open(os.path.join(src, 'layers.json'))); s = info['scale']
    skip = {int(x) for x in info['skip'].split(',') if x}
    M = np.ones((h, w), bool)
    for L in D['layers']:
        if L['index'] in skip and L['index'] != 36 and L['box'][2] - L['box'][0] < D['canvas'][0] * 0.9:
            x0, y0, x1, y1 = [int(round(v * s)) for v in L['box']]; M[max(0, y0):y1, max(0, x0):x1] = False
    err = np.abs(R - C).mean(2)
    rep = {'mean_abs_error': round(float(err[M].mean()), 2), 'texts': {}}
    for L in D['layers']:
        if L['kind'] != 'type' or L['index'] in skip or not L.get('visible', True):
            continue
        x0, y0, x1, y1 = [int(round(v * s)) for v in L['box']]; pad = 6
        bb = [max(0, x0 - pad), max(0, y0 - pad), min(w, x1 + pad), min(h, y1 + pad)]
        bc, br = ink_box(C, bb), ink_box(R, bb)
        if bc and br:
            rep['texts'][L['index']] = {'name': L['name'][:30], 'd_left': int(br[0] - bc[0]), 'd_top': int(br[1] - bc[1]),
                                        'd_right': int(br[2] - bc[2]), 'd_bottom': int(br[3] - bc[3]),
                                        'err': round(float(err[bb[1]:bb[3], bb[0]:bb[2]].mean()), 1)}
    E = np.clip(err * 4, 0, 255).astype(np.uint8)
    board = np.concatenate([C.astype(np.uint8), R.astype(np.uint8), np.stack([E] * 3, 2)], 1)
    Image.fromarray(board).save(out)
    if mk.arg(a, 'json'):
        json.dump(rep, open(mk.arg(a, 'json'), 'w'), indent=1)
    print(f"erreur moyenne {rep['mean_abs_error']} /255 (zones exclues masquées)")
    for k, v in rep['texts'].items():
        print(f"  texte {k:>2} {v['name']:<30} gauche {v['d_left']:+d} haut {v['d_top']:+d} droite {v['d_right']:+d} bas {v['d_bottom']:+d}  err {v['err']}")


if __name__ == '__main__':
    main()
