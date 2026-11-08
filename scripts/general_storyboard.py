"""GENERAL storyboard of the finished film: every scene in order, several key frames per scene with their timecode,
the voice line of the scene, and a one-line description of what happens on each frame (rule 78).

Usage: python3 general_storyboard.py film.mp4 timing.json spec.json out.png [--font Brand.ttf] [--cols 4]
spec.json: {"title": "MTN MoMo — 18 s", "scenes": {"P1": {"name": "Ouverture", "shots": [[frame, "texte"], ...]}, ...}}
The voice line comes from timing.json (scene vo text). Frames are taken from the RENDERED film (what will be delivered).
"""
import os as _o, sys as _s; _s.path.insert(0, _o.path.dirname(_o.path.abspath(__file__))); import _mkpy  # noqa: E401,E702,F401  (bon Python + PATH)
import sys, os, json, textwrap
import cv2
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mkcommon as mk  # noqa: E402


def main():
    a = sys.argv
    if len(a) < 5:
        sys.exit(__doc__)
    film, T, spec, out = a[1], json.load(open(a[2])), json.load(open(a[3])), a[4]
    fpath = mk.arg(a, 'font', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'); cols = mk.arg(a, 'cols', 4, int)
    fps = T['stage']['fps']; TW, TH = 440, 248; PAD = 14
    F = lambda s: ImageFont.truetype(fpath, s)
    cap = cv2.VideoCapture(film); blocks = []
    for sc in T['scenes']:
        sp = spec['scenes'].get(sc['id'])
        if not sp:
            continue
        vo = ' '.join(v.get('text', '') for v in sc.get('vo', []))
        shots = sp['shots']; rows = (len(shots) + cols - 1) // cols
        bh = 70 + rows * (TH + 70); B = Image.new('RGB', (cols * (TW + PAD) + PAD, bh), (24, 24, 28)); d = ImageDraw.Draw(B)
        d.text((PAD, 10), f"{sc['id']}  {sp.get('name', '')}   {sc['new_start']:.2f}–{sc['new_end']:.2f} s", font=F(26), fill=(255, 210, 60))
        d.text((PAD, 42), f"Voix : « {vo} »", font=F(19), fill=(170, 200, 255))
        for i, (fr, txt) in enumerate(shots):
            cap.set(cv2.CAP_PROP_POS_FRAMES, fr); ok, im = cap.read()
            if not ok:
                continue
            x, y = PAD + (i % cols) * (TW + PAD), 70 + (i // cols) * (TH + 70)
            B.paste(Image.fromarray(cv2.cvtColor(im, cv2.COLOR_BGR2RGB)).resize((TW, TH)), (x, y))
            d.rectangle([x, y, x + 92, y + 24], fill=(0, 0, 0)); d.text((x + 6, y + 3), f"{fr / fps:5.2f} s", font=F(17), fill=(255, 255, 255))
            for k, line in enumerate(textwrap.wrap(txt, 46)[:3]):
                d.text((x, y + TH + 6 + k * 20), line, font=F(16), fill=(225, 225, 225))
        blocks.append(B)
    head = Image.new('RGB', (blocks[0].width, 60), (16, 16, 18)); ImageDraw.Draw(head).text((PAD, 14), spec.get('title', ''), font=F(30), fill=(255, 255, 255))
    S = Image.new('RGB', (blocks[0].width, 60 + sum(b.height for b in blocks)), (24, 24, 28)); S.paste(head, (0, 0)); y = 60
    for b in blocks:
        S.paste(b, (0, y)); y += b.height
    S.save(out); print(f'{len(blocks)} scènes -> {out} ({S.size[0]}x{S.size[1]})')


if __name__ == '__main__':
    main()
