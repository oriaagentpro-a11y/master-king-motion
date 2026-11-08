"""Decompose a layered PSD into what the film needs to REBUILD the design identically (rule 82).

Usage: python3 psd_decompose.py design.psd out_dir/ [--scale 1.0]
Writes in out_dir/:
  composite.png         the whole design as Photoshop saved it (the reference to match pixel for pixel)
  layers/NNN_name.png   every pixel / smart-object / shape layer, cropped to its box, with its alpha
  layers.json           for every layer, in stacking order (bottom -> top): name, group path, kind, visible,
                        opacity, blend mode, box [x0, y0, x1, y1] in PSD pixels and normalised to the canvas,
                        and for TEXT layers: the text, font names (PostScript), sizes, colours, tracking, leading,
                        so the text is re-typeset LIVE in code (never pasted as an image)
Notes:
- layer effects (drop shadow, glow, stroke, colour / gradient overlay) are NOT baked by psd-tools: their full values
  are written in `effects_values` (colours, gradient stops with locations, angle, scale, offset) -> rebuild them in
  CSS/SVG from those values (colour overlay on a smart object = CSS mask of the PNG filled with the colour).
- shape layers also get `fill_rgb` (their solid fill), so circles / pills / rectangles are drawn live.
- text sizes are in PSD pixels: in the film, size = psd_px / canvas_height * H (or with the canvas width for a
  different aspect), so the typographic scale of the design is kept.
- the fonts named in layers.json must be loaded in the film (user's files or the closest Google font, named in the report).
"""
import os as _o, sys as _s; _s.path.insert(0, _o.path.dirname(_o.path.abspath(__file__))); import _mkpy  # noqa: E401,E702,F401  (bon Python + PATH)
import sys, os, json, re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mkcommon as mk  # noqa: E402


def plain_desc(v):
    """psd-tools descriptors (dict-like, lists, Enumerated, UnitFloat) -> plain JSON values."""
    if hasattr(v, 'items'):
        return {(k.decode('latin1') if isinstance(k, bytes) else str(k)).strip(): plain_desc(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)) or (hasattr(v, '__iter__') and not isinstance(v, (str, bytes)) and hasattr(v, '__len__')):
        return [plain_desc(x) for x in v]
    if hasattr(v, 'enum'):
        return str(getattr(v.enum, 'value', v.enum)).strip("b' ")
    if hasattr(v, 'value') and not isinstance(v, (int, float, str)):
        return plain_desc(v.value)
    if isinstance(v, bytes):
        return v.decode('latin1')
    return v if isinstance(v, (int, float, str, bool)) or v is None else str(v)


def text_info(layer):
    info = {'text': layer.text}
    try:
        ed = layer.engine_dict; rd = layer.resource_dict
        fonts = [f.get('Name') for f in rd.get('FontSet', [])]
        runs = ed['StyleRun']['RunArray']
        styles = []
        for r in runs:
            s = r['StyleSheet']['StyleSheetData']
            col = s.get('FillColor', {}).get('Values')
            styles.append({'font': fonts[s['Font']] if 'Font' in s and s['Font'] < len(fonts) else None,
                           'size': float(s.get('FontSize', 0)), 'tracking': s.get('Tracking'),
                           'leading': s.get('Leading'), 'fauxBold': s.get('FauxBold'),
                           'color_argb': [round(float(v), 4) for v in col] if col else None})
        info['styles'] = styles
        try:
            info['justification'] = int(ed['ParagraphRun']['RunArray'][0]['ParagraphSheet']['Properties'].get('Justification', 0))
        except Exception:
            info['justification'] = 0   # 0 left, 1 right, 2 centre (around the transform origin x)
        tr = getattr(layer, 'transform', None)
        if tr:
            info['transform'] = [float(v) for v in tr]
    except Exception as e:   # some PSDs store text differently: keep the text and say so
        info['styles_error'] = str(e)
    return info


def main():
    a = sys.argv
    if len(a) < 3:
        sys.exit(__doc__)
    from psd_tools import PSDImage
    psd = PSDImage.open(a[1]); out = a[2]; os.makedirs(os.path.join(out, 'layers'), exist_ok=True)
    W, H = psd.width, psd.height
    psd.composite().save(os.path.join(out, 'composite.png'))
    rows, n = [], 0

    def walk(group, path):
        nonlocal n
        for layer in group:
            if layer.is_group():
                walk(layer, path + [layer.name]); continue
            n += 1
            x0, y0, x1, y1 = layer.bbox
            row = {'index': n, 'name': layer.name, 'group': '/'.join(path), 'kind': layer.kind, 'visible': layer.is_visible(),
                   'opacity': round(layer.opacity / 255, 3), 'blend': str(layer.blend_mode).split('.')[-1],
                   'box': [x0, y0, x1, y1], 'box_norm': [round(x0 / W, 5), round(y0 / H, 5), round(x1 / W, 5), round(y1 / H, 5)]}
            if layer.kind == 'type':
                row.update(text_info(layer))
            try:
                fx = [str(e.__class__.__name__) for e in layer.effects] if layer.has_effects() else []
                if fx:
                    row['effects'] = fx
                    # full values (colour, gradient stops, angle, scale, offset) so the effect is rebuilt exactly
                    row['effects_values'] = {e.__class__.__name__: plain_desc(e.descriptor) for e in layer.effects}
            except Exception as e:
                row['effects_error'] = str(e)
            try:   # shape layers: their solid fill colour (the PNG holds it too, but the film draws shapes live)
                from psd_tools.constants import Tag
                so = layer.tagged_blocks.get_data(Tag.SOLID_COLOR_SHEET_SETTING) if layer.kind == 'shape' else None
                if so is not None:
                    c = plain_desc(so).get('Clr', {})
                    row['fill_rgb'] = [round(c.get('Rd', 0)), round(c.get('Grn', 0)), round(c.get('Bl', 0))]
            except Exception as e:
                row['fill_error'] = str(e)
            if x1 > x0 and y1 > y0:
                try:
                    im = layer.composite()
                    if im is not None:
                        fn = f"{n:03d}_{re.sub(r'[^A-Za-z0-9_-]+', '_', layer.name)[:40]}.png"
                        im.save(os.path.join(out, 'layers', fn)); row['png'] = 'layers/' + fn
                except Exception as e:
                    row['png_error'] = str(e)
            rows.append(row)
    walk(psd, [])
    # psd-tools returns its own String / Bool objects inside engine data: write their plain value
    plain = lambda o: getattr(o, 'value', str(o))
    json.dump({'canvas': [W, H], 'layers': rows}, open(os.path.join(out, 'layers.json'), 'w'), indent=1, ensure_ascii=False, default=plain)
    kinds = {}
    for r in rows:
        kinds[r['kind']] = kinds.get(r['kind'], 0) + 1
    print(f"{a[1]} : {W}x{H}, {len(rows)} calques {kinds} -> {out}")
    for r in rows:
        if r['kind'] == 'type':
            st = (r.get('styles') or [{}])[0]
            print(f"  texte « {str(r['text'])[:40]!s} » police {getattr(st.get('font'), 'value', st.get('font'))} taille {st.get('size')} px")


if __name__ == '__main__':
    main()
