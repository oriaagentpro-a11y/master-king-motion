"""Spotting (règle 143, rôle « real-sfx ») : regarder le MONTAGE image par image et noter chaque moment qui demande un son.

Usage: python3 sfx_cues.py film.html timing.json audio/cues.json [--video out/film_silent.mp4] [--start 0 --end T]
                           [--density 5] [--min-gap 3] [--no-typing] [--debug audio/cues_debug.json]

Le film est ouvert dans Chromium et SEEKÉ à chaque image (window.__rm.seek) : on lit l'état réel de chaque élément
visible (opacité effective, place à l'écran, taille, vitesse, texte) au lieu de deviner. Événements détectés :
  appear   un élément devient visible (opacité effective × part à l'écran passe 0,5)  -> son posé sur cette image (50 %)
  reveal   même chose pour un GRAND élément (≥ 12 % de l'écran : logo, carte héros, écran) -> impact / note
  land     un élément qui bougeait vite s'arrête (contact, fin d'un glissé, d'un zoom)  -> son posé sur l'arrêt
  move     pic de vitesse d'un grand mouvement (caméra, coup de fouet)                   -> souffle (désactivé par défaut,
           règle 141 : « jamais de woosh » sauf demande)
  type     un texte gagne des caractères (frappe)                                        -> une frappe par caractère
           (≤ 12 /s, au-delà une par mot)
  lock     un nombre arrête de changer (compteur qui tombe sur sa valeur finale)         -> déclic
  cut      coupe entre deux scènes (timing.json)                                         -> rien par défaut
Forçage depuis le film : un élément peut porter data-sfx="pop|tick|key|impact|land|lock|chime|swish|none" (le son
voulu, ou aucun) et data-sfx-gain="-6" ; c'est prioritaire sur la détection.
Densité (réf. pro : ~5 effets conçus par 10 s, hors frappes) : on garde les plus forts, les autres sont notés
"skipped": "densite". Jamais deux sons à moins de --min-gap images (règle 142).
--video (le rendu muet) : chaque son d'apparition est recalé sur le pic de différence d'image à ±3 images (règle 142).
Sortie audio/cues.json : {"fps", "duration", "cues": [{id, t, frame, kind, need, el, scene, strength, desc, gain}]}.
`need` est la famille de son à trouver (pop, tick, key, impact, land, lock, chime, swish) : sfx_source.py la cherche,
sfx_place.py la pose. Claude RELIT la liste (et la planche --debug) avant de chercher les sons : supprimer, ajouter,
changer un `need` à la main est normal.
"""
import os as _o, sys as _s; _s.path.insert(0, _o.path.dirname(_o.path.abspath(__file__))); import _mkpy  # noqa: E401,E702,F401  (bon Python + PATH)
import sys, os, json
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mkcommon as mk  # noqa: E402

# JS lu à chaque image : tous les éléments visibles assez grands, avec une clé stable par élément
PROBE_JS = r"""
(() => {
  const W = window.innerWidth, H = window.innerHeight, A = W * H, out = [];
  window.__sfxk = window.__sfxk || new WeakMap(); window.__sfxn = window.__sfxn || 0;
  const eff = el => { let o = 1; for (let e = el; e && e !== document.documentElement; e = e.parentElement) {
      const cs = getComputedStyle(e); if (cs.visibility === 'hidden' || cs.display === 'none') return 0; o *= +cs.opacity; if (o < 0.02) return 0; }
    return o; };
  const all = document.querySelectorAll('body *');
  for (const el of all) {
    const tag = el.tagName; if (tag === 'SCRIPT' || tag === 'STYLE' || tag === 'BR') continue;
    const r = el.getBoundingClientRect(); if (r.width < 2 || r.height < 2) continue;
    const ix = Math.max(0, Math.min(r.right, W) - Math.max(r.left, 0)), iy = Math.max(0, Math.min(r.bottom, H) - Math.max(r.top, 0));
    const area = r.width * r.height, onscr = ix * iy / area;
    if (area / A < 0.0012 || area / A > 0.985) continue;            // trop petit ou plein écran (fond, racine de scène)
    let k = window.__sfxk.get(el); if (k == null) { k = ++window.__sfxn; window.__sfxk.set(el, k); }
    const o = eff(el); if (o * onscr < 0.02 && !el.dataset.sfx) { out.push([k]); continue; }
    const leafText = el.children.length === 0 ? (el.textContent || '').trim() : null;
    out.push([k, +(o * onscr).toFixed(3), +((r.left + r.width / 2) / W).toFixed(4), +((r.top + r.height / 2) / H).toFixed(4),
              +(area / A).toFixed(4), leafText, el.dataset.sfx || null, el.dataset.sfxGain || null,
              el.id || (el.className && typeof el.className === 'string' ? '.' + el.className.split(' ')[0] : tag.toLowerCase())]);
  }
  return out;
})()
"""

NEED_OF = {'appear': 'pop', 'reveal': 'impact', 'land': 'land', 'move': 'swish', 'type': 'key', 'lock': 'lock', 'cut': None}
STRENGTH = {'reveal': 3.0, 'land': 1.6, 'appear': 1.0, 'lock': 1.4, 'move': 1.2, 'type': 0.3, 'cut': 0.0}


def scan(film, T, f0, f1):
    from playwright.sync_api import sync_playwright
    W, H, fps = T['stage']['w'], T['stage']['h'], T['stage']['fps']
    states = []
    with sync_playwright() as pw:
        b = mk.rmcommon.launch(pw); pg = b.new_page(viewport={'width': W, 'height': H})
        pg.goto(mk.rmcommon.scene_url(film, fps, query={'r3d': '0'}))
        pg.wait_for_function('(window.__rm && window.__rm.ready) || !!window.__mk_error', timeout=90000)
        if pg.evaluate('window.__mk_error || null'):
            sys.exit('erreur dans le film : ' + pg.evaluate('window.__mk_error'))
        for k in range(f0, f1):
            pg.evaluate(f'void window.__rm.seek({k / fps})')
            states.append({row[0]: row for row in pg.evaluate(PROBE_JS)})
            if (k - f0) % 150 == 0:
                print(f'  image {k}/{f1}', flush=True)
        b.close()
    return states


def detect(states, f0, fps, typing=True):
    ev = []
    keys = set().union(*[s.keys() for s in states]) if states else set()
    for key in keys:
        vis = np.array([(s.get(key) or [key, 0])[1] if len(s.get(key) or []) > 1 else 0.0 for s in states])
        info = lambda i: states[i].get(key)  # noqa: E731
        cx = np.array([info(i)[2] if info(i) and len(info(i)) > 2 else np.nan for i in range(len(states))])
        cy = np.array([info(i)[3] if info(i) and len(info(i)) > 3 else np.nan for i in range(len(states))])
        ar = np.array([info(i)[4] if info(i) and len(info(i)) > 4 else np.nan for i in range(len(states))])
        last = next((info(i) for i in range(len(states) - 1, -1, -1) if info(i) and len(info(i)) > 2), None)
        if last is None:
            continue
        forced, fgain, name = last[6], last[7], last[8]
        # apparitions : passage de 0,5 vers le haut
        for i in range(1, len(vis)):
            if vis[i - 1] < 0.5 <= vis[i]:
                a = float(np.nanmax(ar[i:i + 15])) if np.any(~np.isnan(ar[i:i + 15])) else 0
                kind = 'reveal' if a >= 0.12 else 'appear'
                ev.append(dict(frame=f0 + i, kind=kind, key=key, el=name, area=a, forced=forced, gain=fgain))
        # vitesse (part de la largeur par image, position + échelle) ; un texte qui change de contenu ne « bouge » pas
        txt = [(info(i)[5] if info(i) and len(info(i)) > 5 else None) for i in range(len(states))]
        sp = np.hypot(np.diff(cx), np.diff(cy) * 9 / 16); sz = np.abs(np.diff(np.log(np.where(ar > 0, ar, np.nan))))
        v = np.nan_to_num(np.fmax(sp, sz * 0.25))
        for i in range(1, len(txt)):
            if txt[i] != txt[i - 1] or vis[i] < 0.5 or vis[i - 1] < 0.5:
                v[i - 1] = 0.0          # changement de texte, ou entrée / sortie (déjà comptée en appear)
        a_med = float(np.nanmedian(ar)) if np.any(~np.isnan(ar)) else 0
        # épisodes de mouvement : v > 0,0015 sur ≥ 3 images, déplacement ≥ 4 % -> « land » à l'arrêt, « move » au pic
        i = 0
        while i < len(v):
            if v[i] <= 0.0015:
                i += 1; continue
            j = i
            while j < len(v) and v[j] > 0.0015:
                j += 1
            seg = v[i:j]
            if j - i >= 3 and seg.sum() >= 0.04 and seg.max() > 0.006:
                if j < len(v):          # il s'arrête dans le film : contact
                    ev.append(dict(frame=f0 + j, kind='land', key=key, el=name, area=a_med, forced=forced, gain=fgain))
                if a_med > 0.05 and seg.max() > 0.04:
                    ev.append(dict(frame=f0 + i + 1 + int(np.argmax(seg)), kind='move', key=key, el=name, area=a_med, forced=forced, gain=fgain))
            i = j
        # textes : frappe et compteurs
        for i in range(1, len(txt)):
            a, b = txt[i - 1], txt[i]
            if a is None or b is None or a == b or vis[i] < 0.5:
                continue
            if typing and b.startswith(a) and 0 < len(b) - len(a) <= 3 and not b.replace(' ', '').isdigit():
                ev.append(dict(frame=f0 + i, kind='type', key=key, el=name, area=0, forced=forced, gain=fgain, ch=b[len(a):]))
            elif any(c.isdigit() for c in b):
                j = i + 1
                while j < len(txt) and txt[j] == b:
                    j += 1
                if j - i >= int(fps * 0.4) and (i < 2 or txt[i - 2] != a):  # le nombre se fige ≥ 0,4 s
                    ev.append(dict(frame=f0 + i, kind='lock', key=key, el=name, area=0, forced=forced, gain=fgain))
    return ev


def dedupe(ev, states, f0):
    """Un parent et ses enfants qui apparaissent ensemble = UN objet = UN son (on garde le plus grand)."""
    ev.sort(key=lambda e: (e['frame'], -e['area']))
    by_key = {}
    for e in ev:
        by_key.setdefault(e['key'], []).append(e)
    out = []
    for e in ev:
        mine = by_key.get(e['key'], [])
        # même objet : l'arrêt qui conclut son entrée (≤ 0,6 s) ne refait pas de son ; un texte tapé sonne par ses frappes
        if not e['forced'] and e['kind'] == 'land' and any(o['kind'] in ('appear', 'reveal') and 0 <= e['frame'] - o['frame'] <= 18 for o in mine):
            continue
        if not e['forced'] and e['kind'] == 'appear' and any(o['kind'] == 'type' and 0 <= o['frame'] - e['frame'] <= 10 for o in mine):
            continue
        if e['kind'] in ('appear', 'reveal', 'land', 'move'):
            if any(o['kind'] in ('appear', 'reveal', 'land', 'move') and abs(o['frame'] - e['frame']) <= 2 and not e['forced']
                   and (o['kind'] == e['kind'] or (e['kind'] == 'appear' and o['kind'] == 'reveal')) for o in out[-40:]):
                continue
        out.append(e)
    return out


def video_peaks(path, fps):
    fr = mk.decode(path, width=320, gray=True)
    d = np.zeros(len(fr))
    d[1:] = [float(np.abs(fr[i].astype(np.float32) - fr[i - 1].astype(np.float32)).mean()) for i in range(1, len(fr))]
    return d


def main():
    a = sys.argv
    if len(a) < 4:
        sys.exit(__doc__)
    film, tp, out = a[1:4]
    T = json.load(open(tp)); fps = T['stage']['fps']
    s = mk.arg(a, 'start', 0.0, float); e = mk.arg(a, 'end', T['total'], float)
    f0, f1 = round(s * fps), round(e * fps)
    gap = mk.arg(a, 'min-gap', 3, int); dens = mk.arg(a, 'density', 5.0, float)
    print(f'Repérage : {f1 - f0} images du film…', flush=True)
    states = scan(film, T, f0, f1)
    ev = dedupe(detect(states, f0, fps, typing='--no-typing' not in a), states, f0)
    for sc in T.get('scenes', [])[1:]:
        ev.append(dict(frame=round(sc['new_start'] * fps), kind='cut', key=None, el=sc.get('id'), area=0, forced=None, gain=None))
    scene_at = lambda f: next((sc.get('id') for sc in T.get('scenes', []) if sc.get('new_start', 0) * fps <= f < sc.get('new_end', 1e9) * fps), None)  # noqa: E731
    if mk.arg(a, 'video'):
        d = video_peaks(mk.arg(a, 'video'), fps)
        for e_ in ev:
            if e_['kind'] in ('appear', 'reveal', 'land') and 0 <= e_['frame'] < len(d):
                lo, hi = max(0, e_['frame'] - 3), min(len(d), e_['frame'] + 4)
                k = lo + int(np.argmax(d[lo:hi]))
                if d[k] > 1.5 * (np.median(d[max(0, k - 15):k + 15]) + 0.05):
                    e_['frame_video'] = k; e_['frame'] = k
    cues, skipped = [], []
    for e_ in sorted(ev, key=lambda x: x['frame']):
        need = e_['forced'] if e_['forced'] else NEED_OF[e_['kind']]
        if e_['kind'] == 'move' and not e_['forced']:
            need = None  # règle 141 : pas de souffle par défaut
        st = STRENGTH[e_['kind']] * (1 + 4 * e_['area'])
        c = dict(t=round(e_['frame'] / fps, 4), frame=e_['frame'], kind=e_['kind'], need=None if need == 'none' else need,
                 el=e_['el'], scene=scene_at(e_['frame']), strength=round(st, 3),
                 gain=float(e_['gain']) if e_['gain'] else None)
        if e_.get('ch'):
            c['ch'] = e_['ch']
        if 'frame_video' in e_:
            c['recale_sur_video'] = True
        (cues if c['need'] else skipped).append(c)
    # frappes : ≤ 12 /s, sinon une par mot ; espaces plus doux
    typed, keep = [c for c in cues if c['kind'] == 'type'], []
    for c in typed:
        if keep and c['frame'] - keep[-1]['frame'] < fps / 12 and c.get('ch', 'x').strip():
            if not (c.get('ch') or '').startswith(' '):
                skipped.append({**c, 'skipped': 'frappe trop rapide (> 12 /s)'}); continue
        if (c.get('ch') or '').strip() == '':
            c['gain'] = (c['gain'] or 0) - 6
        keep.append(c)
    designed = [c for c in cues if c['kind'] != 'type']
    # écart minimal et densité
    designed.sort(key=lambda c: -c['strength'] - (100 if c['gain'] is not None or c['kind'] == 'reveal' else 0))
    chosen = []
    for c in designed:
        if any(abs(c['frame'] - o['frame']) < gap for o in chosen):
            skipped.append({**c, 'skipped': f'à moins de {gap} images d\'un son plus fort'}); continue
        win = [o for o in chosen if abs(o['t'] - c['t']) < 5.0]
        series = any(o['need'] == c['need'] and abs(o['t'] - c['t']) <= 0.6 for o in chosen)  # une série = un geste
        if len(win) >= dens and c['kind'] != 'reveal' and not series:
            skipped.append({**c, 'skipped': 'densite'}); continue
        chosen.append(c)
    final = sorted(chosen + keep, key=lambda c: c['frame'])
    for i, c in enumerate(final):
        c['id'] = f"{c['kind']}:{c['el']}:{i}"
    res = {'fps': fps, 'duration': T['total'], 'film': os.path.abspath(film), 'cues': final,
           'skipped': sorted(skipped, key=lambda c: c['frame'])}
    os.makedirs(os.path.dirname(os.path.abspath(out)) or '.', exist_ok=True)
    json.dump(res, open(out, 'w'), indent=1, ensure_ascii=False)
    if mk.arg(a, 'debug'):
        json.dump(ev, open(mk.arg(a, 'debug'), 'w'), indent=1, ensure_ascii=False, default=str)
    from collections import Counter
    print(f"{len(final)} sons à poser ({dict(Counter(c['need'] for c in final))}), {len(skipped)} moments écartés -> {out}")
    for c in final:
        if c['kind'] != 'type':
            print(f"  {c['t']:7.3f} s  img {c['frame']:5d}  {c['kind']:7s} -> {c['need']:7s} {c['el']}  ({c['scene']})")


if __name__ == '__main__':
    main()
