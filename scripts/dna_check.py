"""Refuse a DNA (or a film) built on guesses.

Usage: python3 dna_check.py <motion_dna.json> [--film film.html] [--strict]
Checks the DNA:
  - every scene has phases, roles (background / accent / text) and a type (notes.json) ;
  - every motion has ease, start, duration, from, to and a source; an rmse too large is listed
    (the move must be replayed frame by frame with RM.trackAt, not with one tween) ;
  - typography is filled (font, weights, source) ;
  - "default-looking" values are flagged: duration exactly 0.5 / 1.0 with power1.out / none and no source.
With --film: every GSAP ease written in the film must exist in the DNA (or be marked // mkm:allow), so
no default ease sneaks into the new video.
Exit code 1 when something blocks (--strict: warnings block too).
"""
import sys, os, re, json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mkcommon as mk  # noqa: E402


def main():
    a = sys.argv
    if len(a) < 2:
        sys.exit(__doc__)
    dna = json.load(open(a[1])); strict = '--strict' in a
    errs, warns = [], []
    for s in dna['scenes']:
        if 'phases' not in s:
            errs.append(f"{s['id']}: pas de phases (relancer dna_build.py)")
        if not s.get('roles'):
            errs.append(f"{s['id']}: pas de rôles de couleur")
        if not s.get('type'):
            warns.append(f"{s['id']}: type de scène non décrit (notes.json → scenes.{s['id']}.type)")
        if s['cut_in'].startswith('transition') and not s.get('transition_in'):
            warns.append(f"{s['id']}: entrée par transition non décrite (notes.json → transition_in : type, durée, ease, source)")
        if 'défaut' in s.get('phases', {}).get('source', ''):
            warns.append(f"{s['id']}: phases par défaut — aucun mouvement mesuré dans la scène (track_*.py + track_fit.py)")
    eases = {'none'}
    dec = {}
    for k, e in dna['elements'].items():
        if not e.get('motions'):
            warns.append(f'élément {k}: aucun mouvement mesuré')
        for m in e.get('motions', []):
            miss = [f for f in ('ease', 'start', 'duration', 'from', 'to') if m.get(f) is None]
            if miss:
                errs.append(f"{k}.{m.get('prop')}: champs manquants {miss}")
                continue
            eases.add(m['ease'].split('(')[0])
            if not m.get('source'):
                errs.append(f"{k}.{m['prop']} à {m['start']} s : pas de source")
            if m['duration'] in (0.5, 1.0) and m['ease'] in ('power1.out', 'none') and 'mesur' not in str(m.get('source', '')):
                warns.append(f"{k}.{m['prop']}: valeurs qui ressemblent à des défauts ({m['ease']} {m['duration']} s)")
            if 'décalquer' in str(m.get('quality', '')):
                dec.setdefault(f"{k}.{m['prop']}", []).append(m['start'])
            if m.get('truncated'):
                warns.append(f"{k}.{m['prop']} à {m['start']} s : coupé par le cadre, fin extrapolée — confirmer à l'œil")
        if not e.get('slot'):
            warns.append(f'élément {k}: aucun emplacement (slot) pour le contenu de l\'utilisateur (notes.json)')
    for k, ts in dec.items():
        pt = any(p['prop'] == k.split('.')[1] for p in dna['elements'][k.split('.')[0]].get('patterns', []))
        warns.append(f"{k}: {len(ts)} mouvement(s) qu'une seule courbe ne décrit pas (dès {ts[0]} s)"
                     + (" — motif répété : vérifier son ease à l'œil image par image (mouvement trop court pour la mesure)" if pt else ' → RM.trackAt'))
    for s in dna['scenes']:
        tr = s.get('transition_in')
        if tr and tr.get('ease'):
            eases.add(tr['ease'].split('(')[0])
    typo = dna.get('typography') or {}
    for f in ('font', 'weights', 'source'):
        if not typo.get(f):
            errs.append(f'typographie : « {f} » manquant (font_search.py, track_textbox.py)')
    film = mk.arg(a, 'film', None)
    if film:
        src = open(film, encoding='utf-8').read()
        for ln, line in enumerate(src.splitlines(), 1):
            if 'mkm:allow' in line:
                continue
            for e in re.findall(r"ease\s*:\s*['\"]([\w.]+)", line):
                if e not in eases:
                    errs.append(f'{os.path.basename(film)}:{ln} ease « {e} » absent de l\'ADN (valeur inventée ?)')
    print(f"ADN : {len(dna['scenes'])} scènes, {len(dna['elements'])} éléments, eases mesurés : {', '.join(sorted(eases))}")
    for e in errs:
        print('  BLOQUANT ', e)
    for w in warns:
        print('  À VOIR   ', w)
    bad = bool(errs) or (strict and bool(warns))
    print('ADN refusé.' if bad else ('ADN valide.' + (f' ({len(warns)} points à voir)' if warns else '')))
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
