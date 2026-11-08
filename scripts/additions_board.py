"""Storyboard of PROPOSED ADDITIONS ("notre plus"): one row per scene = the current frame, and the same frame with
the proposed elements drawn as a MOCK-UP on top (boxes, texts, rings, lines), plus a caption.
For the user to validate BEFORE anything is built (rule 75).

Usage: python3 additions_board.py film.mp4 spec.json out.png [--font Brand.ttf] [--font2 Ref.ttf]
                                 [--base stills_dir --plus stills_dir]   REAL renders instead of drawn mock-ups
(prefer real renders: drawn boxes and loose texts read as amateur and mislead the validation — rule 76)
spec.json: {"scenes": [{"id": "P3", "frame": 280, "title": "...", "caption": "...",
             "draw": [{"type": "text", "xy": [0.12, 0.42], "text": "Votre solde", "size": 0.05, "color": "#0B3A55",
                       "accent": "#FFCC00"},
                      {"type": "line", "from": [0.3, 0.45], "to": [0.55, 0.42], "color": "#FFCC00", "width": 3},
                      {"type": "ring", "xy": [0.5, 0.7], "r": 0.05, "frac": 0.7, "color": "#004F71", "width": 5},
                      {"type": "dots", "xy": [0.5, 0.82], "n": 4, "filled": 3, "r": 0.012, "gap": 0.04, "color": "#004F71"},
                      {"type": "box", "xy": [0.1, 0.1], "wh": [0.2, 0.1], "color": "#FFCC00", "label": "..."}]}]}
Coordinates are normalised to the frame (0-1). Mock-ups show WHERE and WHAT; the motion is described in the caption.
"""
import sys, os, json, textwrap
import cv2
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mkcommon as mk  # noqa: E402


def hexrgb(h):
    h = h.lstrip('#'); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def main():
    a = sys.argv
    if len(a) < 4:
        sys.exit(__doc__)
    film, spec, out = a[1], json.load(open(a[2])), a[3]
    f1 = mk.arg(a, 'font', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'); f2 = mk.arg(a, 'font2', f1)
    TW, TH = 640, 360; rows = []
    cap = cv2.VideoCapture(film)
    for sc in spec['scenes']:
        bdir, pdir = mk.arg(a, 'base'), mk.arg(a, 'plus')
        if bdir:   # REAL renders: current frame | the frame with the additions built in the film (?plus=1)
            base = Image.open(os.path.join(bdir, f"f{sc['frame']:05d}.png")).convert('RGB')
        else:
            cap.set(cv2.CAP_PROP_POS_FRAMES, sc['frame']); ok, im = cap.read()
            base = Image.fromarray(cv2.cvtColor(im, cv2.COLOR_BGR2RGB))
        W, H = base.size
        mock = base.copy().convert('RGBA'); ov = Image.new('RGBA', mock.size, (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
        for e in sc.get('draw', []):
            c = hexrgb(e.get('color', '#FFCC00'))
            if e['type'] == 'text':
                ft = ImageFont.truetype(f1 if e.get('font', 1) == 1 else f2, int(e.get('size', 0.05) * H))
                x, y = e['xy'][0] * W, e['xy'][1] * H
                if e.get('accent'):
                    d.rectangle([x - 0.012 * H, y + 0.1 * e.get('size', 0.05) * H, x - 0.004 * H, y + e.get('size', 0.05) * H * 1.05], fill=hexrgb(e['accent']) + (255,))
                d.text((x, y), e['text'], font=ft, fill=c + (int(255 * e.get('alpha', 1)),))
            elif e['type'] == 'line':
                d.line([e['from'][0] * W, e['from'][1] * H, e['to'][0] * W, e['to'][1] * H], fill=c + (255,), width=e.get('width', 3))
                d.ellipse([e['to'][0] * W - 6, e['to'][1] * H - 6, e['to'][0] * W + 6, e['to'][1] * H + 6], fill=c + (255,))
            elif e['type'] == 'ring':
                x, y, r = e['xy'][0] * W, e['xy'][1] * H, e['r'] * H
                d.ellipse([x - r, y - r, x + r, y + r], outline=c + (60,), width=e.get('width', 5))
                d.arc([x - r, y - r, x + r, y + r], -90, -90 + 360 * e.get('frac', 0.7), fill=c + (255,), width=e.get('width', 5))
            elif e['type'] == 'dots':
                x0 = e['xy'][0] * W - (e['n'] - 1) * e['gap'] * H / 2; y = e['xy'][1] * H; r = e['r'] * H
                for i in range(e['n']):
                    x = x0 + i * e['gap'] * H
                    if i < e.get('filled', 0):
                        d.ellipse([x - r, y - r, x + r, y + r], fill=c + (255,))
                    else:
                        d.ellipse([x - r, y - r, x + r, y + r], outline=c + (255,), width=3)
            elif e['type'] == 'box':
                x, y, w, h = e['xy'][0] * W, e['xy'][1] * H, e['wh'][0] * W, e['wh'][1] * H
                d.rounded_rectangle([x, y, x + w, y + h], radius=int(0.02 * H), outline=c + (255,), width=4)
                if e.get('label'):
                    d.text((x + 10, y + 8), e['label'], font=ImageFont.truetype(f1, int(0.028 * H)), fill=c + (255,))
        mock = Image.alpha_composite(mock, ov).convert('RGB')
        if pdir:
            mock = Image.open(os.path.join(pdir, f"f{sc['frame']:05d}.png")).convert('RGB')
        row = Image.new('RGB', (2 * TW + 30 + 520, TH + 50), (24, 24, 28)); dr = ImageDraw.Draw(row)
        row.paste(base.resize((TW, TH)), (10, 40)); row.paste(mock.resize((TW, TH)), (TW + 20, 40))
        hf = ImageFont.truetype(f1, 22); cf = ImageFont.truetype(f1, 17)
        title, fs_ = f"{sc['id']}  {sc.get('title', '')}", 22   # shrink the title to its column (it overlapped the label)
        while fs_ > 12 and dr.textlength(title, font=ImageFont.truetype(f1, fs_)) > TW - 4:
            fs_ -= 1
        dr.text((10, 8), title, font=ImageFont.truetype(f1, fs_), fill=(255, 210, 60))
        dr.text((TW + 20, 8), 'PROPOSITION' + (' (rendu réel)' if pdir else ' (maquette)'), font=cf, fill=(160, 200, 255))
        y = 44
        for para in sc.get('caption', '').split('\n'):
            for line in textwrap.wrap(para, 52) or ['']:
                dr.text((2 * TW + 34, y), line, font=cf, fill=(230, 230, 230)); y += 22
        rows.append(row)
    S = Image.new('RGB', (rows[0].width, sum(r.height for r in rows)), (24, 24, 28)); y = 0
    for r in rows:
        S.paste(r, (0, y)); y += r.height
    S.save(out); print(f'{len(rows)} scènes -> {out}')


if __name__ == '__main__':
    main()
