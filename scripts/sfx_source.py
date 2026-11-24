"""Trouver LE bon son pour chaque besoin (règle 143) : Openverse (sons réels sous licence libre) + earshot (écoute,
classement, génération si rien ne convient).

Usage: python3 sfx_source.py audio/cues.json audio/ [--per-query 10] [--keep 3] [--needs pop,impact]
                             [--brief "doux, feutré, premium"] [--no-openverse] [--no-make] [--offline]

Pour chaque famille de son demandée par cues.json (`need` : pop, tick, key, impact, land, lock, chime, swish) :
 1. Openverse (api.openverse.org, ~ millions de sons Freesound / Wikimedia / Jamendo) : plusieurs recherches par
    famille, licences filtrées CC0 / domaine public / CC BY UNIQUEMENT (NC, ND, SA refusées : film commercial),
    durée bornée ; téléchargement poli (un fichier à la fois, 1 s d'écart) dans audio/assets/openverse/<need>/.
 2. earshot `find` découpe dans chaque enregistrement les meilleurs passages pour la description (un seul coup,
    pas la prise entière) -> candidats WAV 48 kHz dans audio/assets/candidates/<need>/.
 3. earshot `make` rend aussi 3 sons de son catalogue pour la même description (candidats « générés »).
 4. earshot `rank` écoute TOUS les candidats (modèle CLAP) et les classe ; verdict strong / plausible / weak / no match.
 5. Si le meilleur n'est pas au moins « plausible » : earshot `build` construit un son NEUF à partir de ses parties
    enregistrées, on le réécoute avec les autres et on garde le meilleur (marqué "faible" si rien n'atteint plausible).
Sortie audio/sfx_library.json : need -> {choice, alternates (variantes pour ne jamais répéter le même son), source,
licence, attribution, z, verdict} et audio/CREDITS_SFX.md (crédits CC BY obligatoires dans la description de la
vidéo). Claude regarde le classement, peut forcer un autre candidat (`"choice"`) et relancer sfx_place.py.
--brief ajoute le caractère du film aux recherches (ex. « soft », « glass », « wood ») : palette cohérente.
"""
import os as _o, sys as _s; _s.path.insert(0, _o.path.dirname(_o.path.abspath(__file__))); import _mkpy  # noqa: E401,E702,F401  (bon Python + PATH)
import sys, os, json, time, re, subprocess, urllib.request, urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mkcommon as mk  # noqa: E402

API = 'https://api.openverse.org/v1/audio/'
UA = 'master-king-motion-sfx/1.0 (open source motion design tool)'
OK_LIC = {'cc0', 'pdm', 'by'}           # commercial + modification autorisés ; by = crédit obligatoire

# need : (recherches Openverse, description CLAP (vocabulaire d'earshot), demande earshot make, durée max du coup en s)
NEEDS = {
    'pop':    (['ui pop', 'bubble pop', 'pop sound effect'],            'a chat message pop',                   'a soft ui pop', 0.6),
    'tick':   (['ui click', 'interface click', 'button click'],        'a crisp interface click',              'a soft ui click', 0.35),
    'key':    (['keyboard key press', 'typing keyboard', 'keystroke'],  'a single mechanical keyboard key press', 'a single soft keyboard key press', 0.3),
    'impact': (['cinematic impact', 'impact hit', 'boom hit'],         'a punchy impact hit',                  'a deep soft cinematic impact', 2.5),
    'land':   (['soft thud', 'thump', 'body fall soft'],               'a heavy thud',                         'a soft muted thud', 0.8),
    'lock':   (['latch click', 'switch click', 'lock click'],          'a latch clicking shut',                'a crisp latch click', 0.5),
    'chime':  (['chime', 'glass ting', 'success chime'],               'a success chime',                      'a soft success chime', 3.0),
    'swish':  (['swish', 'swoosh', 'whoosh short'],                    'a short swish',                        'a short soft swish', 1.2),
}
RANK = {'strong': 3, 'plausible': 2, 'weak': 1, 'no match': 0}


def get_json(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def openverse(query, n, max_ms):
    q = urllib.parse.urlencode({'q': query, 'license': ','.join(sorted(OK_LIC)), 'page_size': min(20, max(n * 2, 10)),
                                'mature': 'false'})
    try:
        res = get_json(API + '?' + q).get('results', [])
    except Exception as e:  # noqa: BLE001
        print(f'  Openverse indisponible pour « {query} » : {e}'); return []
    keep = []
    for r in res:
        if r.get('license') not in OK_LIC or not r.get('url'):
            continue
        d = r.get('duration') or 0
        if d and d > max_ms:
            continue
        if (r.get('category') or '') == 'music':
            continue
        keep.append(r)
    return keep[:n]


def download(r, folder):
    ext = (r.get('filetype') or os.path.splitext(urllib.parse.urlparse(r['url']).path)[1].lstrip('.') or 'mp3')[:5]
    slug = re.sub(r'[^a-z0-9]+', '-', (r.get('title') or 'son').lower())[:40].strip('-')
    path = os.path.join(folder, f"ov-{r['id'][:8]}_{slug}.{ext}")
    if not os.path.exists(path):
        req = urllib.request.Request(r['url'], headers={'User-Agent': UA})
        with urllib.request.urlopen(req, timeout=60) as resp, open(path, 'wb') as f:
            f.write(resp.read())
        time.sleep(1.0)
    return path


def cut(src, dst, start, end):
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', src, '-ss', f'{start:.4f}', '-to', f'{end:.4f}',
                    '-ar', '48000', '-ac', '2', '-af', 'afade=t=out:st={:.4f}:d=0.01'.format(max(0, end - start - 0.01)),
                    dst], check=True)


def main():
    a = sys.argv
    if len(a) < 3:
        sys.exit(__doc__)
    C = json.load(open(a[1])); root = a[2]
    per_q = mk.arg(a, 'per-query', 6, int); keep_n = mk.arg(a, 'keep', 3, int); brief = mk.arg(a, 'brief', '')
    needs = sorted({c['need'] for c in C['cues'] if c.get('need')})
    if mk.arg(a, 'needs'):
        needs = [n for n in mk.arg(a, 'needs').split(',')]
    from earshot import api
    lib_path = os.path.join(root, 'sfx_library.json')
    lib = json.load(open(lib_path)) if os.path.exists(lib_path) else {}
    for need in needs:
        if need not in NEEDS:
            print(f'! famille inconnue « {need} » : ajouter une ligne dans NEEDS (sfx_source.py) ou corriger cues.json'); continue
        queries, clap, make_req, maxd = NEEDS[need]
        print(f'\n== {need} : « {clap} »', flush=True)
        cand_dir = os.path.join(root, 'assets', 'candidates', need); os.makedirs(cand_dir, exist_ok=True)
        meta = {}
        # 1-2. Openverse -> passages découpés par earshot find
        if '--no-openverse' not in a and '--offline' not in a:
            ov_dir = os.path.join(root, 'assets', 'openverse', need); os.makedirs(ov_dir, exist_ok=True)
            seen = set()
            for q in queries:
                for r in openverse((brief + ' ' + q).strip(), per_q, max(4000, maxd * 1000 * 8)):
                    if r['id'] in seen:
                        continue
                    seen.add(r['id'])
                    try:
                        src = download(r, ov_dir)
                        segs = api.find(src, clap, top=3).get('segments', [])
                    except Exception as e:  # noqa: BLE001
                        print(f'  écarté {r.get("title")!r} : {e}'); continue
                    # un passage qui coupe dans un son (« head cut ») attaque mal : seulement s'il n'y a rien d'autre
                    clean = [sg for sg in segs if 'head cut' not in (sg.get('cut') or '')]
                    segs = (clean or segs)[:2]
                    for j, sg in enumerate(segs):
                        s0, s1 = float(sg['start']), float(sg['end'])
                        s1 = min(s1, s0 + maxd)
                        dst = os.path.join(cand_dir, f"ov-{r['id'][:8]}_{j}.wav")
                        try:
                            cut(src, dst, max(0.0, s0 - 0.005), s1)
                        except Exception:  # noqa: BLE001
                            continue
                        meta[os.path.basename(dst)] = {
                            'source': 'openverse', 'provider': r.get('source'), 'title': r.get('title'), 'creator': r.get('creator'),
                            'license': r.get('license'), 'license_version': r.get('license_version'),
                            'license_url': r.get('license_url'), 'page': r.get('foreign_landing_url'), 'download': r.get('url'),
                            'attribution': r.get('attribution'), 'trim': [round(s0, 3), round(s1, 3)], 'file_original': src}
            print(f'  Openverse : {len(seen)} enregistrements, {len(meta)} passages candidats')
        # 3. earshot make : candidats générés
        if '--no-make' not in a:
            try:
                r = api.make(make_req, out=os.path.join(cand_dir, f'earshot-{need}.wav'), n=3, seed=7)
                for f in r['files']:
                    meta[os.path.basename(f)] = {'source': 'earshot make', 'design': r.get('sound'), 'license': 'libre (rendu earshot, MIT)'}
            except Exception as e:  # noqa: BLE001
                print(f'  earshot make a échoué : {e}')
        if not meta:
            print('  aucun candidat'); continue
        # 4. écoute et classement
        ranked = api.rank([os.path.join(cand_dir, f) for f in meta], clap)['results']
        best = ranked[0] if ranked else None
        # 5. rien de plausible -> on construit un son neuf
        if '--no-make' not in a and (not best or RANK.get(best['verdict'], 0) < 2):
            print(f"  meilleur = {best and best['name']} ({best and best['verdict']}) : construction d'un son neuf (earshot build)…", flush=True)
            try:
                out = os.path.join(cand_dir, f'earshot-build-{need}.wav')
                api_build = __import__('earshot.build', fromlist=['build']).build
                api_build(make_req, out=out)
                meta[os.path.basename(out)] = {'source': 'earshot build', 'license': 'libre (rendu earshot, MIT)'}
                ranked = api.rank([os.path.join(cand_dir, f) for f in meta], clap)['results']
            except Exception as e:  # noqa: BLE001
                print(f'  earshot build a échoué : {e}')
        top = ranked[:max(1, keep_n)]
        pick = lambda r: {**meta.get(r['name'], {}), 'file': os.path.relpath(os.path.join(cand_dir, r['name']), root).replace('\\', '/'),  # noqa: E731
                          'z': r['z'], 'verdict': r['verdict'], 'sounds_most_like': r.get('sounds_most_like')}
        lib[need] = {'description': clap, 'choice': pick(top[0]), 'alternates': [pick(r) for r in top[1:]],
                     'faible': RANK.get(top[0]['verdict'], 0) < 2,
                     'classement': [{'file': r['name'], 'z': r['z'], 'verdict': r['verdict'],
                                     'source': meta.get(r['name'], {}).get('source')} for r in ranked]}
        for r in ranked[:6]:
            print(f"  {r['z']:+.2f} {r['verdict']:10s} {r['name']:32s} {meta.get(r['name'], {}).get('source')}")
        print(f"  -> choisi : {top[0]['name']} ({top[0]['verdict']})" + ('  [FAIBLE : à écouter / remplacer]' if lib[need]['faible'] else ''))
        json.dump(lib, open(lib_path, 'w'), indent=1, ensure_ascii=False)
    # crédits
    lines = ['# Crédits des effets sonores', '', 'Sons réels trouvés via Openverse (openverse.org). Les sons CC BY doivent être',
             'crédités dans la description de la vidéo (copier les lignes ci-dessous).', '']
    for need, e in lib.items():
        for it in [e['choice']] + e['alternates']:
            if it.get('source') == 'openverse':
                lines.append(f"- {it.get('attribution') or it.get('title')}  ({it.get('license')} {it.get('license_version') or ''}, {it.get('page')})")
    lines += ['', 'Sons générés par earshot (github.com/Leonxlnx/earshot, MIT) : libres, sans crédit obligatoire.']
    open(os.path.join(root, 'CREDITS_SFX.md'), 'w').write('\n'.join(lines) + '\n')
    print(f'\nBibliothèque -> {lib_path} ; crédits -> {os.path.join(root, "CREDITS_SFX.md")}')


if __name__ == '__main__':
    main()
