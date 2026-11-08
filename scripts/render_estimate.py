"""Estimate how long a Blender job will take BEFORE launching it, so the user is told the duration.

Usage: python3 scripts/render_estimate.py job.json [--frame N]
Renders ONE frame of the job (the middle one by default) into a temp folder with the same settings
(GPU used automatically when present), times it, and prints the device, seconds per frame and the total.
The first frame of a run also pays the scene build / shader compilation, so it is subtracted once.
"""
import os, sys, json, time, shutil, subprocess, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def blender_exe():
    for b in [os.environ.get('BLENDER'), os.path.join(ROOT, 'blender', 'app', 'blender.exe'),
              os.path.join(ROOT, 'blender', 'app', 'blender'), shutil.which('blender')]:
        if b and os.path.exists(b):
            return b
    sys.exit('Blender introuvable : lancer python3 scripts/ensure_ready.py')


def run(job_path, still):
    t = time.time()
    r = subprocess.run([blender_exe(), '-b', '-P', os.path.join(ROOT, 'blender', 'render_job.py'), '--', job_path],
                       capture_output=True, text=True)
    dev = next((l.split(' ', 1)[1] for l in r.stdout.splitlines() if l.startswith('MKM_DEVICE')), '?')
    if r.returncode != 0:
        sys.exit('échec du rendu de test :\n' + (r.stderr or r.stdout)[-800:])
    return time.time() - t, dev


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    src = os.path.abspath(sys.argv[1]); J = json.load(open(src)); base = os.path.dirname(src)
    frames = J['frames']; total = len(frames) if not J.get('render_frames') else J['render_frames'][1] - J['render_frames'][0] + 1
    f = int(sys.argv[sys.argv.index('--frame') + 1]) if '--frame' in sys.argv else frames[len(frames) // 2]['f']
    tmp = tempfile.mkdtemp(prefix='mkm-est-')
    try:
        for k in ('hdri', 'icon'):   # keep relative paths valid from the temp job
            if isinstance(J.get(k), str) and not os.path.isabs(J[k]):
                J[k] = os.path.join(base, J[k])
        if isinstance(J.get('icon'), dict) and not os.path.isabs(J['icon'].get('face', '/')):
            J['icon']['face'] = os.path.join(base, J['icon']['face'])
        scr = J.get('screen', {})
        for k in ('pattern', 'image'):
            if k in scr and not os.path.isabs(scr[k]):
                scr[k] = os.path.join(base, scr[k])
        for c in J.get('cards', []):
            if not os.path.isabs(c['image']):
                c['image'] = os.path.join(base, c['image'])
        J['out'] = os.path.join(tmp, 'f_####.png')
        J1 = dict(J, still=f); p1 = os.path.join(tmp, 'one.json'); json.dump(J1, open(p1, 'w'))
        t1, dev = run(p1, f)
        J2 = dict(J, still=None, render_frames=[f, min(f + 1, frames[-1]['f'])]); p2 = os.path.join(tmp, 'two.json')
        json.dump(J2, open(p2, 'w'))
        t2, _ = run(p2, None)
        n2 = J2['render_frames'][1] - J2['render_frames'][0] + 1
        per = max(0.5, (t2 - t1) / max(1, n2 - 1)) if n2 > 1 else t1
        setup = max(0.0, t1 - per)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    tot = setup + per * total
    print(f'appareil : {dev}')
    print(f'≈ {per:.1f} s par image, {total} images, préparation {setup:.0f} s')
    print(f'DURÉE ESTIMÉE : {int(tot // 60)} min {int(tot % 60):02d} s')


if __name__ == '__main__':
    main()
