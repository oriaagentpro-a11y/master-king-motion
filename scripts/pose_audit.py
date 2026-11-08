"""Audit the poses of a Blender job BEFORE rendering: frozen stretches and snaps (rule 71).

Usage: python3 pose_audit.py job.json [--fps 30] [--min-speed 15] [--min-hold 0.3] [--snap 12] [--first-frame N]
                             [--allow f0-f1,f2-f3]   film frames where a STILL object is the reference's own choice
                             (e.g. a flat tile that stays still while dots orbit it): reported, not counted
- frozen: the object is visible and its rotation changes by less than --min-speed deg/s (and its size by less than
  8 %/s, its position by less than 5 %/s: slower reads as still on screen) for longer than --min-hold seconds -> it reads as STUCK on screen.
- snap: the rotation changes by more than --snap degrees in one frame AND more than 2.5x the neighbouring frames
  (a fast continuous spin is not a snap) -> a jump (e.g. a logo straightening in one frame at a collapse).
- tilted-and-still (DEFECT): face turned > 20 deg while rotating slower than --min-speed for > --min-hold.
- tilt: visible frames where |rx| or |ry| > 25 deg for longer than --min-hold: a flat face (logo, screen) seen
  sideways stays hard to read (warning only; a phone in a 3/4 shot can be intended).
--first-frame: film frame of job frame 1 (to print film frames / times). Exit code 1 when a frozen stretch or a snap
is found. Multi-object jobs ("poses") are audited object by object.
"""
import sys, os, json, math
ALLOW = []

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mkcommon as mk  # noqa: E402


def audit(frames, fps, mins, hold, snap, f0, label):
    bad = 0; vis = [fr for fr in frames if fr['p']['z'] > -40 and fr['p']['z'] < 0]
    rot = lambda p: (p.get('rx', 0), p.get('ry', 0), p.get('rz', 0))
    run = []

    def flush():
        nonlocal bad
        if len(run) / fps >= hold:
            a, b = run[0], run[-1]
            if any(lo <= f0 + a - 1 and f0 + b - 1 <= hi for lo, hi in ALLOW):
                print(f"  voulu  {label} immobile images film {f0 + a - 1}-{f0 + b - 1} (déclaré comme dans la référence)"); return
            print(f"  FIGÉ   {label} images film {f0 + a - 1}-{f0 + b - 1} ({(f0 + a - 1) / fps:.2f}-{(f0 + b - 1) / fps:.2f} s, {len(run) / fps:.2f} s)")
            bad += 1
    for i in range(1, len(vis)):
        p, q = vis[i - 1]['p'], vis[i]['p']
        if vis[i]['f'] != vis[i - 1]['f'] + 1:
            flush(); run = []; continue
        dr = max(abs(x - y) for x, y in zip(rot(p), rot(q)))
        dz = abs(q['z'] - p['z']) / abs(p['z']); dxy = math.hypot(q['x'] - p['x'], q['y'] - p['y']) / abs(p['z'])
        # a SNAP is a spike against the neighbours (a fast continuous spin is not a snap)
        nb = []
        for j in (i - 1, i + 1):
            if 1 <= j < len(vis) and vis[j]['f'] == vis[j - 1]['f'] + 1:
                nb.append(max(abs(x - y) for x, y in zip(rot(vis[j - 1]['p']), rot(vis[j]['p']))))
        if dr > snap and (not nb or dr > 2.5 * max(nb)):
            print(f"  SAUT   {label} image film {f0 + vis[i]['f'] - 1} : {dr:.1f} deg en une image (voisines {', '.join(f'{x:.1f}' for x in nb)})"); bad += 1
        # perceived as STILL: slow rotation AND slow size / position change (a 5 %/s shrink reads as still)
        if dr * fps < mins and dz * fps < 0.08 and dxy * fps < 0.05:
            run.append(vis[i]['f'])
        else:
            flush(); run = []
    flush()
    # TILTED AND NOT TURNING (user's complaint): face seen sideways (> 20 deg) while the rotation is slower than
    # --min-speed, for longer than --min-hold, whatever the size does -> a defect
    tr_ = []
    for i in range(1, len(vis)):
        p, q = vis[i - 1]['p'], vis[i]['p']
        side = max(abs(q.get('rx', 0)), abs(q.get('ry', 0))) > 20
        slow = max(abs(x - y) for x, y in zip(rot(p), rot(q))) * fps < mins and vis[i]['f'] == vis[i - 1]['f'] + 1
        if side and slow:
            tr_.append(vis[i]['f'])
        else:
            if len(tr_) / fps >= hold:
                print(f"  PENCHÉ-IMMOBILE {label} images film {f0 + tr_[0] - 1}-{f0 + tr_[-1] - 1} ({len(tr_) / fps:.2f} s)"); bad += 1
            tr_ = []
    if len(tr_) / fps >= hold:
        print(f"  PENCHÉ-IMMOBILE {label} images film {f0 + tr_[0] - 1}-{f0 + tr_[-1] - 1} ({len(tr_) / fps:.2f} s)"); bad += 1
    tilted = [fr['f'] for fr in vis if abs(fr['p'].get('rx', 0)) > 25 or abs(fr['p'].get('ry', 0)) > 25]
    if len(tilted) / fps >= hold:
        print(f"  biais  {label} : {len(tilted)} images vues de biais (> 25 deg) — lisible ? (avertissement)")
    return bad


def main():
    a = sys.argv
    if len(a) < 2:
        sys.exit(__doc__)
    J = json.load(open(a[1])); fps = mk.arg(a, 'fps', J.get('fps', 30), float)
    mins, hold, snap = mk.arg(a, 'min-speed', 15, float), mk.arg(a, 'min-hold', 0.3, float), mk.arg(a, 'snap', 12, float)
    f0 = mk.arg(a, 'first-frame', 1, int); bad = 0
    global ALLOW
    ALLOW = [tuple(int(v) for v in r.split('-')) for r in (mk.arg(a, 'allow') or '').split(',') if r]
    if J['frames'] and 'poses' in J['frames'][0]:
        for k in range(len(J['frames'][0]['poses'])):
            bad += audit([{'f': fr['f'], 'p': fr['poses'][k]} for fr in J['frames']], fps, mins, hold, snap, f0, f'objet {k}')
    else:
        bad += audit([{'f': fr['f'], 'p': fr['pose']} for fr in J['frames']], fps, mins, hold, snap, f0, 'objet')
    print('poses : OK' if not bad else f'poses : {bad} défaut(s)')
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
