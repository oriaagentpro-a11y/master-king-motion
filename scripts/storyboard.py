"""Storyboard to VALIDATE with the user before the full render: reference vs new video, scene by scene.

Usage: python3 storyboard.py <timing.json> <film.html> <reference.mp4> <out_dir> [--keys 3]
For each plan scene, the same moments are shown side by side (reference frame | new frame):
  entrance (mid-way), entrance finished, hold, exit — taken at the SAME reference-local times, the new ones
  through the warp knots, so the user sees the reference move applied to their content.
Writes out_dir/storyboard.png (one row per scene, with timing, voice-over text and slots) and
out_dir/storyboard.md (the same as a table, to paste in the conversation). Only a few stills are rendered:
it takes seconds, the full render comes after the user's "OK".
"""
import sys, os, json
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mkcommon as mk  # noqa: E402
from render_film import stills  # noqa: E402

FONT = os.path.join(HERE, '..', 'engine', 'Outfit-var.ttf')


def to_new(k, x):
    for i in range(1, len(k)):
        if x <= k[i][0]:
            p, q = k[i - 1], k[i]; sp = q[0] - p[0]
            return q[1] if sp <= 1e-9 else p[1] + (x - p[0]) * (q[1] - p[1]) / sp
    return k[-1][1] + x - k[-1][0]


def font(sz, wt=500):
    try:
        f = ImageFont.truetype(FONT, sz); f.set_variation_by_axes([wt]); return f
    except Exception:  # noqa: BLE001
        return ImageFont.load_default()


def wrap(d, txt, f, w):
    out, line = [], ''
    for word in str(txt).split():
        t = (line + ' ' + word).strip()
        if d.textlength(t, font=f) > w and line:
            out.append(line); line = word
        else:
            line = t
    return out + ([line] if line else [])


def main():
    a = sys.argv
    if len(a) < 5:
        sys.exit(__doc__)
    T = json.load(open(a[1])); film, ref, out = a[2], a[3], a[4]
    os.makedirs(out, exist_ok=True)
    fps = T['stage']['fps']; R = mk.probe(ref)
    rows, md = [], ['| Plan | Réf. | Temps | Voix off | Contenu |', '|---|---|---|---|---|']
    keys_all, new_frames = [], []
    for s in T['scenes']:
        k = s['knots']; ph = s['ref_phases']; in_end, out_start, D = ph['in_end'], ph['out_start'], ph['duration']
        ks = [('entrée', in_end * 0.5), ('posé', min(in_end + 0.1, D - 0.02))]
        ks.append(('pause', (in_end + out_start) / 2) if out_start - in_end > 0.3 else ('pause', min(in_end + 0.3, D - 0.02)))
        if out_start < D - 0.05:
            ks.append(('sortie', (out_start + D) / 2))
        if s.get('rhythm'):
            r = s['rhythm']; n = r['count']
            ks = [(f'élément {i + 1}', r['first_rel'] + i * r['every_s'] + min(r['duration_s'], r['every_s'] * 0.6))
                  for i in sorted({0, n // 2, n - 1})]
        ks = ks[:max(2, mk.arg(a, 'keys', 4, int))]
        lst = []
        for lab, tr in ks:
            tr_ref = tr
            if s.get('rhythm'):  # reference item i at the reference interval (the new one follows the new tempo)
                i = int(lab.split()[-1]) - 1
                tr_ref = s['rhythm']['first_rel'] + i * s['rhythm'].get('ref_every_s', s['rhythm']['every_s']) + (tr - s['rhythm']['first_rel'] - i * s['rhythm']['every_s'])
            tr_ref = min(tr_ref, s['ref_end'] - s['ref_start'] - 0.04)
            Rs = mk.probe(s.get('source') or ref)
            fr_ref = min(Rs['frames'] - 1, round((s['ref_start'] + tr_ref) * Rs['fps']))
            # a key frame always shows ITS scene: never on or after the cut
            fr_new = max(s['new_start_frame'], min(s['new_end_frame'] - 2, T['total_frames'] - 1, round((s['new_start'] + to_new(k, tr)) * fps)))
            lst.append((lab, tr, fr_ref, fr_new, s.get('source') or ref)); new_frames.append(fr_new)
        keys_all.append(lst)
    sd = os.path.join(out, 'stills')
    stills(film, T, sorted(set(new_frames)), sd)
    tw = 360; th_r = int(tw * R['h'] / R['w']); th_n = int(tw * T['stage']['h'] / T['stage']['w']); th = max(th_r, th_n)
    lab_w = 300; f_b, f_s, f_t = font(22, 700), font(15, 400), font(13, 500)
    for s, lst in zip(T['scenes'], keys_all):
        im = Image.new('RGB', (lab_w + len(lst) * (2 * tw + 16), th + 34), (16, 16, 20)); d = ImageDraw.Draw(im)
        d.text((12, 8), f"{s['id']}  ←  réf. {s['ref']}", font=f_b, fill=(255, 255, 255))
        d.text((12, 38), f"{s['new_start']:.2f}–{s['new_end']:.2f} s ({s['duration']:.2f} s)", font=f_s, fill=(200, 200, 210))
        y = 60
        vo = ' / '.join(p.get('text') or f"phrase {p['i']}" for p in s['vo'])
        for ln in wrap(d, ('VO : ' + vo) if vo else 'sans voix off', f_s, lab_w - 20)[:5]:
            d.text((12, y), ln, font=f_s, fill=(255, 210, 120)); y += 19
        sl = {k: (v.get('value') or v.get('src') or '') if isinstance(v, dict) else v for k, v in s['slots'].items() if k not in ('colors',)}
        for ln in wrap(d, ' · '.join(f'{k}: {v}' for k, v in sl.items()), f_s, lab_w - 20)[:6]:
            d.text((12, y), ln, font=f_s, fill=(170, 220, 255)); y += 19
        x = lab_w
        for lab, tr, fr, fn, srcv in lst:
            r = mk.read_frame(srcv, fr)
            if r is not None:
                im.paste(Image.fromarray(r).resize((tw, th_r), Image.LANCZOS), (x, 30))
            n = Image.open(os.path.join(sd, f'f{fn:05d}.png')).convert('RGB').resize((tw, th_n), Image.LANCZOS)
            im.paste(n, (x + tw + 4, 30))
            d.text((x + 4, 8), f'{lab} · réf. {os.path.basename(srcv)[:14]} {fr / mk.probe(srcv)["fps"]:.2f} s', font=f_t, fill=(160, 160, 170))
            d.text((x + tw + 8, 8), f'nouveau {fn / fps:.2f} s', font=f_t, fill=(120, 230, 160))
            x += 2 * tw + 16
        rows.append(im)
        md.append(f"| {s['id']} | {s['ref']} | {s['new_start']:.2f}–{s['new_end']:.2f} s | {vo or '—'} | "
                  + ' · '.join(f'{k}: {v}' for k, v in sl.items()) + ' |')
    Wt = max(r.width for r in rows); Ht = sum(r.height for r in rows) + 8 * len(rows) + 60
    big = Image.new('RGB', (Wt, Ht), (8, 8, 10)); d = ImageDraw.Draw(big)
    d.text((12, 14), f"Storyboard — {T['total']:.2f} s, {T['stage']['w']}x{T['stage']['h']}, {fps:g} i/s  "
                     f"(gauche : référence, droite : nouvelle vidéo)", font=f_b, fill=(255, 255, 255))
    y = 60
    for r in rows:
        big.paste(r, (0, y)); y += r.height + 8
    p = os.path.join(out, 'storyboard.png'); big.save(p)
    md.insert(0, f"**Storyboard** — durée {T['total']:.2f} s, {T['stage']['w']}×{T['stage']['h']}, {fps:g} i/s, calage musique : {T['snap']}\n")
    if T.get('warnings'):
        md += ['', '**Points à trancher :**'] + [f'- {w}' for w in T['warnings']]
    open(os.path.join(out, 'storyboard.md'), 'w', encoding='utf-8').write('\n'.join(md) + '\n')
    print(f'storyboard -> {p} + storyboard.md ({len(rows)} scènes)')


if __name__ == '__main__':
    main()
