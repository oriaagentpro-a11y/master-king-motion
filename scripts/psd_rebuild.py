"""Rebuild a decomposed PSD (psd_decompose.py) as an HTML page: pixel layers as PNG <img> with their blend mode and
opacity, colour overlays as CSS masks, shape layers drawn live (solid fill), TEXT LAYERS RE-TYPESET LIVE with the real
font, size, tracking, leading, justification and origin (rule 84). Then compare it with composite.png (psd_compare).

Usage: python3 psd_rebuild.py analysis/psd out.html --fonts assets/fonts [--scale 0.25]
                              [--skip 9,36] [--text 15="/reverse-motion          /master-motion          /Thought"]
                              [--grad-flip]
- --skip: layers left out (a logo that must not be used, a flattened copy of the whole poster…). They are also listed
  in out.html's data-skip so the comparison masks their boxes.
- --text i="…": corrected text for layer i (typo) - the rest of its style is kept.
- text geometry: font-size = size x transform scale; origin = transform (tx, ty) = baseline of the FIRST line;
  justification 0 left / 1 right / 2 centre around tx; tracking/1000 em = letter-spacing; leading x scale = line step.
- --nudge i=dx,dy,dtrack: residual fix for one text (a font build slightly different from the designer's): read the
  edge errors of psd_compare (rebuild - PSD, poster px) -> dx = -(dl + dr)/2 / scale, dtrack = (dl - dr) / (gaps x size).
- --grain amount: adds the film grain of the flattened poster (a top layer often holds a noise filter).
- every element gets id="L<index>" and class "psd-layer", so the film animates the SAME elements (no re-layout).
"""
import os as _o, sys as _s; _s.path.insert(0, _o.path.dirname(_o.path.abspath(__file__))); import _mkpy  # noqa: E401,E702,F401  (bon Python + PATH)
import sys, os, json, html

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mkcommon as mk  # noqa: E402

BLEND = {'NORMAL': 'normal', 'SCREEN': 'screen', 'SOFT_LIGHT': 'soft-light', 'MULTIPLY': 'multiply', 'OVERLAY': 'overlay',
         'LINEAR_DODGE': 'plus-lighter', 'LIGHTEN': 'lighten', 'DARKEN': 'darken', 'COLOR_DODGE': 'color-dodge',
         'HARD_LIGHT': 'hard-light', 'DIFFERENCE': 'difference', 'COLOR': 'color', 'LUMINOSITY': 'luminosity',
         'HUE': 'hue', 'SATURATION': 'saturation', 'PASS_THROUGH': 'normal'}


def rgb(c):
    return f"rgb({round(c.get('Rd', 0))},{round(c.get('Grn', 0))},{round(c.get('Bl', 0))})"


def main():
    a = sys.argv
    if len(a) < 3:
        sys.exit(__doc__)
    src, out = a[1], a[2]; D = json.load(open(os.path.join(src, 'layers.json')))
    W, H = D['canvas']; s = mk.arg(a, 'scale', 0.25, float); fdir = mk.arg(a, 'fonts', 'assets/fonts')
    skip = {int(x) for x in mk.arg(a, 'skip', '').split(',') if x}
    texts = {}
    for i, x in enumerate(a):
        if x == '--text':
            k, v = a[i + 1].split('=', 1); texts[int(k)] = v
    flip = '--grad-flip' in a
    nudge = {}   # --nudge i=dx,dy,dtrack : PSD px and tracking units, from psd_compare's per-text edge errors
    for i, x in enumerate(a):
        if x == '--nudge':
            k, v = a[i + 1].split('='); nudge[int(k)] = [float(u) for u in v.split(',')]
    rel = os.path.relpath(src, os.path.dirname(os.path.abspath(out)))
    frel = os.path.relpath(fdir, os.path.dirname(os.path.abspath(out)))
    fonts = set(); els = []
    for L in D['layers']:
        i = L['index']
        if i in skip or not L.get('visible', True):
            continue
        x0, y0, x1, y1 = L['box']; op = L.get('opacity', 1); bl = BLEND.get(L.get('blend', 'NORMAL'), 'normal')
        base = f"position:absolute;opacity:{op};mix-blend-mode:{bl};"
        fx = L.get('effects_values', {})
        if L['kind'] == 'type':
            st = (L.get('styles') or [{}])[0]; tr = L.get('transform') or [1, 0, 0, 1, x0, y1]
            k = tr[0]; size = st['size'] * k; font = str(st['font']); fonts.add(font)
            lead = (st.get('leading') or st['size'] * 1.2) * k
            txt = texts.get(i, L['text']).replace('\r', '\n').split('\n')
            just = L.get('justification', 0); tx, ty = tr[4], tr[5]
            ndx, ndy, ndt = nudge.get(i, [0, 0, 0]); tx += ndx; ty += ndy
            track = (st.get('tracking') or 0) + ndt
            col = 'rgb(%d,%d,%d)' % tuple(round(255 * v) for v in (st.get('color_argb') or [1, 1, 1, 1])[1:4])
            paint = f"color:{col};"
            g = fx.get('GradientOverlay'); gattr = ''
            if g:   # gradient overlay: laid out by the page script on the layer's INK box (what Photoshop uses)
                gd = {'stops': [[rgb(c['Clr']), c['Lctn'] / 4096] for c in g['Grad']['Clrs']], 'angle': g.get('Angl', 90),
                      'scale': g.get('Scl', 100) / 100, 'off': [g.get('Ofst', {}).get('Hrzn', 0) / 100, g.get('Ofst', {}).get('Vrtc', 0) / 100],
                      'box': [v * s for v in L['box']], 'flip': flip}
                gattr = f" data-grad='{json.dumps(gd)}'"
            pad = size * s   # spans padded (and pulled back by negative margins) so background-clip:text never cuts the glyphs
            lines = ''.join(f'<div style="height:{lead * s:.2f}px"><span style="display:inline-block;padding:{pad:.1f}px 0;margin:-{pad:.1f}px 0">{html.escape(t)}</span></div>' for t in txt)
            anchor = {0: '0', 1: '-100%', 2: '-50%'}[just]
            els.append(f'<div id="L{i}" class="psd-layer psd-text" data-name="{html.escape(L["name"])}" style="{base}left:{tx * s:.2f}px;'
                       f'top:{ty * s:.2f}px;transform:translate({anchor},calc(-0.5 * ({lead * s:.3f}px - (var(--asc-{font}) + var(--dsc-{font})) * {size * s:.3f}px) - var(--asc-{font}) * {size * s:.3f}px));'
                       f'font-family:\'{font}\';font-size:{size * s:.3f}px;line-height:{lead * s:.2f}px;'
                       f'letter-spacing:{track / 1000:.4f}em;white-space:pre;text-align:{["left", "right", "center"][just]};'
                       f'{paint}"{gattr}>{lines}</div>')
            continue
        if x1 <= x0 or y1 <= y0:
            continue
        box = f"left:{x0 * s:.2f}px;top:{y0 * s:.2f}px;width:{(x1 - x0) * s:.2f}px;height:{(y1 - y0) * s:.2f}px;"
        png = L.get('png'); co = fx.get('ColorOverlay')
        if co and png:      # colour overlay on a smart object / pixel layer: the PNG is the mask, the colour the paint
            u = f"{rel}/{png}"
            els.append(f'<div id="L{i}" class="psd-layer" style="{base}{box}background:{rgb(co["Clr"])};opacity:{op * co.get("Opct", 100) / 100};'
                       f'-webkit-mask:url({u}) center/100% 100% no-repeat;mask:url({u}) center/100% 100% no-repeat"></div>')
        elif png:
            els.append(f'<img id="L{i}" class="psd-layer" src="{rel}/{png}" style="{base}{box}">')
    grain = mk.arg(a, 'grain', 0, float)
    if grain:   # fixed-seed fractal noise in soft-light over everything (the film animates its seed per frame)
        els.append(f'<svg id="grain" class="psd-layer" width="100%" height="100%" style="position:absolute;inset:0;mix-blend-mode:soft-light;opacity:{grain};pointer-events:none">'
                   '<filter id="gn"><feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed="3"/>'
                   '<feColorMatrix type="saturate" values="0"/></filter><rect width="100%" height="100%" filter="url(#gn)"/></svg>')
    faces = ''.join(f"@font-face{{font-family:'{f}';src:url('{frel}/{f}.ttf')}}" for f in sorted(fonts))
    # ascender / descender of each font (hhea, what Chrome uses) so the CSS line box puts the baseline exactly on ty:
    # baseline in a line box = (line-height - (asc + desc) x size) / 2 + asc x size
    from fontTools.ttLib import TTFont
    asc = []
    for f in sorted(fonts):
        try:
            t = TTFont(os.path.join(fdir, f + '.ttf')); hh = t['hhea']; upm = t['head'].unitsPerEm
            asc.append(f"--asc-{f}:{hh.ascent / upm:.4f};--dsc-{f}:{-hh.descent / upm:.4f}")
        except Exception as e:
            print('police manquante', f, e); asc.append(f"--asc-{f}:0.8;--dsc-{f}:0.2")
    open(out, 'w').write(f"""<!doctype html><html><head><meta charset="utf-8"><style>{faces}
html,body{{margin:0;background:#000}} #poster{{position:relative;overflow:hidden;width:{W * s:.0f}px;height:{H * s:.0f}px;isolation:isolate;{';'.join(asc)}}}
.psd-text div{{line-height:inherit}} .psd-text{{transform-origin:0 0}}
</style></head><body><div id="poster" data-skip="{','.join(map(str, sorted(skip)))}" data-scale="{s}">
{chr(10).join(els)}
</div><script>
// gradient overlays: Photoshop lays the gradient on the layer's ink box, centred + offset, length = box extent x scale
document.fonts.ready.then(() => document.querySelectorAll('[data-grad]').forEach(el => {{
  const g = JSON.parse(el.dataset.grad), P = document.getElementById('poster').getBoundingClientRect();
  const [x0, y0, x1, y1] = g.box, a = g.angle * Math.PI / 180, dx = Math.cos(a), dy = -Math.sin(a);
  const ext = Math.abs(dx) * (x1 - x0) + Math.abs(dy) * (y1 - y0), L = ext * g.scale;
  const cx = (x0 + x1) / 2 + g.off[0] * (x1 - x0), cy = (y0 + y1) / 2 + g.off[1] * (y1 - y0);
  el.querySelectorAll('span').forEach(sp => {{
    const r = sp.getBoundingClientRect(), ox = r.left - P.left, oy = r.top - P.top;
    let st = g.stops.map(([c, t]) => [c, g.flip ? 1 - t : t]);
    // start point of the gradient (t = 0) in poster px, then in span px
    const sx = cx - dx * L / 2 - ox, sy = cy - dy * L / 2 - oy;
    // CSS stops must be in increasing order along the CSS line: sorted below. CSS: angle measured clockwise from 'to top'; the gradient line passes through the box centre:
    const css = 90 - g.angle, w = r.width, h = r.height, ca = (css) * Math.PI / 180;
    const glen = Math.abs(w * Math.sin(ca)) + Math.abs(h * Math.cos(ca));
    const gx0 = w / 2 - Math.sin(ca) * glen / 2, gy0 = h / 2 + Math.cos(ca) * glen / 2;   // CSS gradient line start
    const pos = t => ((sx + dx * L * t - gx0) * Math.sin(ca) + (sy + dy * L * t - gy0) * -Math.cos(ca));
    sp.style.background = `linear-gradient(${{css}}deg, ${{st.map(([c, t]) => [c, pos(t)]).sort((u, v) => u[1] - v[1]).map(([c, q]) => c + ' ' + q.toFixed(1) + 'px').join(',')}})`;
    sp.style.webkitBackgroundClip = 'text'; sp.style.backgroundClip = 'text'; sp.style.color = 'transparent';
  }}); el.style.background = 'none';
}}));
</script></body></html>""")
    print(f'{len(els)} éléments -> {out} ({W * s:.0f}x{H * s:.0f}), polices {sorted(fonts)}')


if __name__ == '__main__':
    main()
