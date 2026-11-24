"""Découpe la piste téléphone d'un film (engine/export_phone.mjs) en jobs Blender Cycles (blender/render_job.py), règle 135.

Usage: python3 phone_jobs.py phone_track.json out_dir [--colors '{"frame":"#A9A8C2",...}'] [--dims '{"aspect":0.493,"depth":0.06}']
                             [--samples 64] [--W 1080 --H 1920] [--blur 0.2] [--still n1,n2,...] [--engine EEVEE|CYCLES] [--missing]
- --missing : reprise après un arrêt (PC éteint) : ne garde que les jobs qui ont des images absentes, et ne rend que celles-là
- un job par suite d'images CONSÉCUTIVES ayant la même prise et le même écran (l'écran est une image fixe du job) ;
- images numérotées n+1 (n = image du film) : out_dir/frames/f_####.png ; le film les relit avec window.PHONE_SEQ ;
- --still : ne rend QUE ces images du film (storyboard), chacune dans le job qui la contient (toutes les poses gardées
  pour la continuité du flou de mouvement) ;
- écrit out_dir/jobs.txt (une commande Blender par ligne) et out_dir/phone_seq.js (table n -> chemin, images existantes).
"""
import os as _o, sys as _s; _s.path.insert(0, _o.path.dirname(_o.path.abspath(__file__))); import _mkpy  # noqa: E401,E702,F401
import sys, os, json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mkcommon as mk  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    a = sys.argv
    if len(a) < 3:
        sys.exit(__doc__)
    T = json.load(open(a[1], encoding='utf-8')); out = os.path.abspath(a[2]); os.makedirs(out, exist_ok=True)
    tdir = os.path.dirname(os.path.abspath(a[1]))
    fr = {int(n): v for n, v in T['frames'].items()}; ns = sorted(fr)
    runs, cur = [], []
    for n in ns:
        if cur and (n != cur[-1] + 1 or fr[n]['shot'] != fr[cur[-1]]['shot'] or fr[n]['screen'] != fr[cur[-1]]['screen']):
            runs.append(cur); cur = []
        cur.append(n)
    runs.append(cur)
    colors = json.loads(mk.arg(a, 'colors', '{}')); dims = json.loads(mk.arg(a, 'dims', '{}'))
    stills = set(int(x) for x in mk.arg(a, 'still', '').split(',') if x)
    blender = os.path.join(ROOT, 'blender', 'app', 'blender.exe' if os.name == 'nt' else 'blender')
    cmds = []
    for i, r in enumerate(runs):
        r0 = fr[r[0]]; key = r0['screen'].replace('|', '_')
        key = ''.join(ch if ch.isalnum() or ch in '._-' else '_' for ch in r0['screen'])
        job = {'W': mk.arg(a, 'W', 1080, int), 'H': mk.arg(a, 'H', 1920, int), 'fps': T.get('fps', 30), 'fov': r0['fov'],
               'out': os.path.join(out, 'frames', 'f_####.png'), 'samples': mk.arg(a, 'samples', 64, int),
               'motion_blur': mk.arg(a, 'blur', 0.2, float), 'hdri': os.path.join(ROOT, 'engine', 'hdri', 'studio_small_08_2k.hdr'),
               'hdri_strength': 1.0, 'colors': colors, 'dims': dims, 'shadow': None, 'engine': mk.arg(a, 'engine', 'CYCLES'),
               'screen': {'image': os.path.join(tdir, 'screens', key + '.png')},
               'frames': [{'f': n + 1, 'pose': fr[n]['pose']} for n in r]}
        want = sorted(stills & set(r)) if stills else None
        if stills and not want:
            continue
        if '--missing' in a:   # reprise après arrêt : seules les images absentes (toutes les poses gardées : flou continu)
            have = {int(fn[2:6]) for fn in os.listdir(os.path.join(out, 'frames'))} if os.path.isdir(os.path.join(out, 'frames')) else set()
            miss = [n + 1 for n in r if n + 1 not in have]
            if not miss:
                continue
            job['render_frames'] = [min(miss), max(miss)]
        jobs = [dict(job, still=n + 1) for n in want] if want else [job]
        for k, j in enumerate(jobs):
            p = os.path.join(out, f'job_{i:02d}_{r0["shot"]}' + (f'_s{k}' if want else '') + '.json')
            json.dump(j, open(p, 'w', encoding='utf-8'), indent=0)
            cmds.append(f'"{blender}" -b -P "{os.path.join(ROOT, "blender", "render_job.py")}" -- "{p}"')
    open(os.path.join(out, 'jobs.txt'), 'w', encoding='utf-8').write('\n'.join(cmds) + '\n')
    # lanceur : une commande Blender après l'autre (une seule à la fois : 1 rendu lourd par machine, règle 92) ;
    # < /dev/null : un programme qui lit l'entrée standard ne doit pas avaler les lignes suivantes (règle 105)
    open(os.path.join(out, 'run_jobs.sh'), 'w', encoding='utf-8', newline='\n').write(
        '#!/bin/bash\n' + ''.join(f'{c} < /dev/null > /dev/null 2>&1\n' for c in cmds))
    # table image du film -> PNG rendu, relue par la page (window.PHONE_SEQ) ; à régénérer après le rendu
    frames_dir = os.path.join(out, 'frames')
    seq = {int(fn[2:6]) - 1: os.path.relpath(os.path.join(frames_dir, fn), mk.arg(a, 'page-dir', os.getcwd())).replace('\\', '/')
           for fn in (os.listdir(frames_dir) if os.path.isdir(frames_dir) else []) if fn.startswith('f_') and fn.endswith('.png')}
    open(os.path.join(out, 'phone_seq.js'), 'w', encoding='utf-8').write('window.PHONE_SEQ=' + json.dumps(seq) + ';\n')
    print(len(runs), 'suites,', len(cmds), 'jobs ->', os.path.join(out, 'jobs.txt'))


if __name__ == '__main__':
    main()
