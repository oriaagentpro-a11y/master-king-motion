"""Poser chaque son EXACTEMENT sur son image (règle 143) : cues.json + sfx_library.json -> piste d'effets WAV.

Usage: python3 sfx_place.py audio/cues.json audio/sfx_library.json audio/sfx.wav [--root audio/]
                            [--gains pop=-8,key=-16] [--seed 3] [--sheet audio/sfx_sheet.json]
Puis : finalize.py out/film_silent.mp4 out/final.mp4 --music … --voice … --sfx audio/sfx.wav --timing timing.json
Contrôle : python -m earshot timeline out/final.mp4 --cues audio/cues.json   (le son du fichier FINI, entendu)

Calage : l'ATTAQUE mesurée du son (premier échantillon à -20 dB de son pic) tombe sur l'image du repère ; un souffle
(swish) et un impact (souvent précédé d'un pré-souffle) ont leur PIC sur l'image.
Variété : jamais deux fois de suite le même fichier pour une même famille (choix + alternatives en rotation),
±1 demi-ton et ±1,5 dB aléatoires (graine fixe) sur les sons répétés (frappes, pops en série).
Niveaux par défaut (dB, avant finalize --sfx-db) : impact -3, chime -6, land -8, pop -9, lock -9, tick -11, swish -12,
key -17 (règle 141 : coups répétés 10-19 dB plus bas) ; un `gain` dans le repère (data-sfx-gain) s'ajoute.
Une série rapprochée (≥ 3 pops / ticks à < 0,25 s) monte de +0,5 demi-ton à chaque coup (escalier, pas de mitraillette).
Fondus 3 ms début / 15 ms fin, aucun clic. Sortie 48 kHz stéréo, exactement la durée du film ; feuille de coups
(--sheet) : image, temps, fichier, gain, demi-tons — la trace de chaque son posé.
"""
import os as _o, sys as _s; _s.path.insert(0, _o.path.dirname(_o.path.abspath(__file__))); import _mkpy  # noqa: E401,E702,F401  (bon Python + PATH)
import sys, os, json, subprocess, wave
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mkcommon as mk  # noqa: E402

SR = 48000
LEVEL = {'impact': -3, 'chime': -6, 'land': -8, 'pop': -9, 'lock': -9, 'tick': -11, 'swish': -12, 'key': -17}


def load(path):
    p = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-f', 'f32le', '-acodec', 'pcm_f32le', '-ac', '2', '-ar', str(SR), '-'],
                       capture_output=True, check=True)
    x = np.frombuffer(p.stdout, dtype=np.float32).reshape(-1, 2).astype(np.float64)
    pk = np.abs(x).max()
    return x / pk if pk > 0 else x


def attack(x):
    env = np.abs(x).max(axis=1); thr = env.max() * 0.1
    return int(np.argmax(env >= thr))


def resample(x, semis):
    if abs(semis) < 1e-3:
        return x
    r = 2 ** (semis / 12); n = int(len(x) / r); idx = np.arange(n) * r
    return np.stack([np.interp(idx, np.arange(len(x)), x[:, c]) for c in range(2)], axis=1)


def fades(x):
    a, b = min(len(x), int(0.003 * SR)), min(len(x), int(0.015 * SR))
    x = x.copy(); x[:a] *= np.linspace(0, 1, a)[:, None]; x[-b:] *= np.linspace(1, 0, b)[:, None]
    return x


def main():
    a = sys.argv
    if len(a) < 4:
        sys.exit(__doc__)
    C = json.load(open(a[1])); L = json.load(open(a[2])); out = a[3]
    root = mk.arg(a, 'root', os.path.dirname(os.path.abspath(a[2])))
    lv = dict(LEVEL)
    for kv in (mk.arg(a, 'gains', '') or '').split(','):
        if '=' in kv:
            k, v = kv.split('='); lv[k] = float(v)
    rng = np.random.default_rng(mk.arg(a, 'seed', 3, int))
    dur = float(C['duration']); n = int(round(dur * SR)); mix = np.zeros((n, 2))
    cache, last, sheet, missing = {}, {}, [], set()
    cues = sorted(C['cues'], key=lambda c: c['t'])
    for i, c in enumerate(cues):
        need = c.get('need')
        if not need:
            continue
        e = L.get(need)
        if not e:
            missing.add(need); continue
        pool = [e['choice']] + e.get('alternates', [])
        k = (last.get(need, -1) + 1) % len(pool); last[need] = k
        f = os.path.join(root, pool[k]['file'])
        if f not in cache:
            cache[f] = load(f)
        x = cache[f]
        # série rapprochée -> escalier ; sons répétés -> micro-variations
        run = 0
        for p in reversed(cues[:i]):
            if p.get('need') == need and c['t'] - p['t'] < 0.25 * (run + 1):
                run += 1
            else:
                break
        semis = 0.0; g = lv.get(need, -10) + (c.get('gain') or 0)
        if need in ('key', 'pop', 'tick') or run:
            semis = float(rng.uniform(-1, 1)) * (0.5 if need == 'key' else 1.0); g += float(rng.uniform(-1.5, 1.5))
        if need in ('pop', 'tick') and run >= 2:
            semis += 0.5 * run
        y = fades(resample(x, semis)) * 10 ** (g / 20)
        if need in ('swish', 'impact'):   # un impact peut avoir un pré-souffle : c'est son PIC qui tombe sur l'image
            anchor = int(np.argmax(np.abs(y).max(axis=1)))
        else:
            anchor = attack(y)
        s = int(round(c['t'] * SR)) - anchor
        a0, b0 = max(0, s), min(n, s + len(y))
        if b0 > a0:
            mix[a0:b0] += y[a0 - s:b0 - s]
        sheet.append({'frame': c['frame'], 't': c['t'], 'need': need, 'file': pool[k]['file'], 'gain_db': round(g, 2),
                      'semitones': round(semis, 2), 'attaque_s': round(anchor / SR, 4), 'el': c.get('el')})
    pk = np.abs(mix).max()
    if pk > 0.89:  # marge : finalize normalise ensuite tout le mix
        mix *= 0.89 / pk
    os.makedirs(os.path.dirname(os.path.abspath(out)) or '.', exist_ok=True)
    with wave.open(out, 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(mix, -1, 1) * 32767).astype('<i2').tobytes())
    sp = mk.arg(a, 'sheet', os.path.join(os.path.dirname(os.path.abspath(out)), 'sfx_sheet.json'))
    json.dump(sheet, open(sp, 'w'), indent=1, ensure_ascii=False)
    print(f'{len(sheet)} sons posés sur {dur:.2f} s -> {out} (feuille : {sp})')
    if missing:
        print('! familles sans son choisi (lancer sfx_source.py) : ' + ', '.join(sorted(missing)))
    print(f'Contrôle : python -m earshot timeline <final.mp4> --cues {a[1]}')


if __name__ == '__main__':
    main()
