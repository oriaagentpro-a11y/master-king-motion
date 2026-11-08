"""Lisse TOUTES les pistes mesurées d'un dossier de pistes JS (window.X = {...}) sans déplacer un seul instant (règle 110).

Usage: python3 smooth_tracks.py dossier_tracks/ [--win 7] [--order 3] [--only a.js,b.js] [--backup dossier_raw/]
Toute table {image: valeur} (clés numériques, >= win images contiguës) est une piste ; valeurs acceptées : nombre,
liste (de listes) de nombres, objet de nombres (les champs non numériques sont laissés tels quels). Filtre
Savitzky-Golay par plage contiguë (les null coupent la plage) : il retire le bruit de mesure image à image (le corps
qui « respire », les positions qui vibrent) en gardant les courbes d'accélération, les départs et les arrivées.
Les sauts réels (coupe, fouet) coupent la piste en morceaux (pas > max(4 x --keep, 8 x pas médian)) ; chaque
morceau est lissé en entier : jamais de valeur brute isolée entre des valeurs lissées (cela crée un cran).
"""
import sys, os, json, re, shutil
import numpy as np
from scipy.signal import savgol_filter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mkcommon as mk  # noqa: E402

WIN, ORD, KEEP = 7, 3, 6.0


def is_track(d):
    return isinstance(d, dict) and len(d) >= WIN and all(re.fullmatch(r'-?\d+', k) for k in d)


def flat(v):
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return [float(v)], None
    if isinstance(v, list):
        out, shp = [], []
        for x in v:
            f, s = flat(x)
            if f is None:
                return None, None
            out += f; shp.append(s if s is not None else 0)
        return out, ('L', shp)
    if isinstance(v, dict):
        ks = [k for k, x in v.items() if isinstance(x, (int, float)) and not isinstance(x, bool)]
        return [float(v[k]) for k in ks], ('D', ks)
    return None, None


def unflat(vals, shp, orig):
    if shp is None:
        return round(vals[0], 3)
    if shp[0] == 'D':
        o = dict(orig)
        for k, x in zip(shp[1], vals):
            o[k] = round(x, 3)
        return o
    out, i = [], 0
    for x, s in zip(orig, shp[1]):
        f, ss = flat(x); n = len(f)
        out.append(unflat(vals[i:i + n], ss, x)); i += n
    return out


def smooth_track(d):
    ks = sorted(d, key=int); n = 0
    run = []
    def flush(run):
        nonlocal n
        if len(run) < WIN:
            return
        rows = [flat(d[k]) for k in run]
        if any(r[0] is None for r in rows):
            return
        L = len(rows[0][0])
        if L == 0:
            return
        if any(r[0] is None or len(r[0]) != L for r in rows):
            return
        A = np.array([r[0] for r in rows]); S = A.copy()
        # coupure aux VRAIES discontinuités (coupe, fouet) : |pas| > max(KEEP*4, 8 x pas médian) sur une composante ;
        # chaque morceau est lissé en entier (jamais de valeur brute isolée au milieu de valeurs lissées = cran)
        dA = np.abs(np.diff(A, axis=0)); med = np.median(dA, axis=0) + 1e-6
        cut = np.where((dA > np.maximum(KEEP * 4, 8 * med)).any(axis=1))[0] + 1
        for seg in np.split(np.arange(len(A)), cut):
            if len(seg) >= WIN:
                S[seg] = savgol_filter(A[seg], WIN, ORD, axis=0, mode='interp')
            elif len(seg) >= 3:
                S[seg] = savgol_filter(A[seg], len(seg) if len(seg) % 2 else len(seg) - 1, 1, axis=0, mode='interp')
        for k, r, v in zip(run, rows, S):
            d[k] = unflat(list(v), r[1], d[k])
        n += len(run)
    for k in ks:
        if d[k] is None or (run and int(k) != int(run[-1]) + 1):
            flush(run); run = []
        if d[k] is not None:
            run.append(k)
    flush(run)
    return n


def walk(o):
    n = 0
    if is_track(o):
        return smooth_track(o)
    if isinstance(o, dict):
        for v in o.values():
            n += walk(v)
    elif isinstance(o, list):
        for v in o:
            n += walk(v)
    return n


def main():
    global WIN, ORD, KEEP
    a = sys.argv
    if len(a) < 2:
        sys.exit(__doc__)
    WIN = mk.arg(a, 'win', 7, int); ORD = mk.arg(a, 'order', 3, int); KEEP = mk.arg(a, 'keep', 6.0, float)
    d = a[1]; only = mk.arg(a, 'only', None); bk = mk.arg(a, 'backup', None)
    files = only.split(',') if only else sorted(f for f in os.listdir(d) if f.endswith('.js'))
    for fn in files:
        p = os.path.join(d, fn); t = open(p).read()
        parts = re.split(r'(window\.\w+\s*=\s*)', t)
        if len(parts) < 3:
            continue
        if bk:
            os.makedirs(bk, exist_ok=True)
            if not os.path.exists(os.path.join(bk, fn)):
                shutil.copy(p, os.path.join(bk, fn))
        out, tot = [parts[0]], 0
        for i in range(1, len(parts), 2):
            body = parts[i + 1].strip(); tail = ''
            m = re.match(r'(.*?);?\s*(/\*.*)?$', body, re.S)
            js = re.sub(r'/\*.*?\*/', '', body, flags=re.S).strip().rstrip(';').strip()
            try:
                o = json.loads(js)
            except Exception:
                out += [parts[i], parts[i + 1]]; continue
            tot += walk(o)
            out += [parts[i], json.dumps(o, ensure_ascii=False) + ';\n']
        open(p, 'w').write(''.join(out))
        print(f'{fn}: {tot} valeurs lissées')


if __name__ == '__main__':
    main()
