"""Create a Master King Motion project folder (one per video to produce).

Usage: python3 new_project.py <project_dir> --ref reference.mp4 [--ref2 other.mp4 ...]
                              [--music m.mp3] [--voice v.wav] [--script s.txt] [--assets file ...]
                              [--format 16:9|9:16|1:1|4:5] [--fps 30]
Creates:
  project/ref/            the reference video(s) (copied)
  project/assets/         the user's files (logo, images, fonts, music, voice-over, script)
  project/analysis/       dissect.py / track_*.py / dna_build.py outputs
  project/plan.json       content map to fill (phase 2), stage size from --format (16:9 = 1920x1080 by default)
  project/notes.json      what the eye sees, to fill while dissecting (phase 1)
  project/film.html       the film skeleton, already wired to the engine
  project/out/            renders, reports, final video
"""
import os as _o, sys as _s; _s.path.insert(0, _o.path.dirname(_o.path.abspath(__file__))); import _mkpy  # noqa: E401,E702,F401  (bon Python + PATH)
import sys, os, json, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import mkcommon as mk  # noqa: E402

SIZES = {'16:9': (1920, 1080), '9:16': (1080, 1920), '1:1': (1080, 1080), '4:5': (1080, 1350), '21:9': (2560, 1080)}


def main():
    a = sys.argv
    if len(a) < 2 or a[1].startswith('--'):
        sys.exit(__doc__)
    d = os.path.abspath(a[1])
    for sub in ('ref', 'assets', 'analysis', 'out'):
        os.makedirs(os.path.join(d, sub), exist_ok=True)
    refs = []
    for i, x in enumerate(a):
        if x.startswith('--ref') and i + 1 < len(a):
            dst = os.path.join(d, 'ref', os.path.basename(a[i + 1])); shutil.copy2(a[i + 1], dst); refs.append(os.path.relpath(dst, d))
    assets = {}
    for k in ('music', 'voice', 'script'):
        if mk.arg(a, k):
            dst = os.path.join(d, 'assets', os.path.basename(mk.arg(a, k))); shutil.copy2(mk.arg(a, k), dst); assets[k] = os.path.relpath(dst, d)
    if '--assets' in a:
        for x in a[a.index('--assets') + 1:]:
            if x.startswith('--'):
                break
            shutil.copy2(x, os.path.join(d, 'assets', os.path.basename(x)))
    fmt = mk.arg(a, 'format', '16:9'); w, h = SIZES.get(fmt, SIZES['16:9'])
    plan = {'stage': {'w': w, 'h': h, 'fps': mk.arg(a, 'fps', 30, int)}, 'format': fmt,
            'references': refs, 'dna': 'analysis/motion_dna.json', 'audio': assets,
            'brand': {'colors': {'background': '#000000', 'accent': '#FFFFFF', 'text': '#FFFFFF'},
                      'fonts': [{'family': 'Brand', 'src': 'REMPLIR (assets/... .ttf ou police Google téléchargée)', 'weight': '100 900'}]},
            'voice_offset': 0.5, 'lead': 0.15, 'pad_after': 0.35, 'min_hold': 0.4, 'tail': 1.2, 'snap': None,
            'scenes': [{'id': 'P01', 'ref': 'S01', 'vo': [0], 'slots': {'titre': {'type': 'text', 'value': 'REMPLIR'}}}]}
    for name, obj in (('plan.json', plan), ('notes.json', {'scenes': {}, 'typography': {}, 'elements': {}, 'finish': {}, 'rules': []})):
        p = os.path.join(d, name)
        if not os.path.exists(p):
            mk.save_json(obj, p)
    fp = os.path.join(d, 'film.html')
    if not os.path.exists(fp):
        eng = os.path.join(ROOT, 'engine').replace(os.sep, '/')
        src = open(os.path.join(ROOT, 'templates', 'film.html'), encoding='utf-8').read().replace('{{ENGINE}}', 'file://' + ('' if eng.startswith('/') else '/') + eng)
        open(fp, 'w', encoding='utf-8').write(src)
    print(f'projet prêt : {d}  (format {fmt} = {w}x{h})')
    print('  références :', ', '.join(refs) or '(aucune : --ref)')
    print('  audio      :', ', '.join(f'{k}={v}' for k, v in assets.items()) or '(aucun)')


if __name__ == '__main__':
    main()
