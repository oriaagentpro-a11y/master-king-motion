"""Print only the golden rules needed NOW, from references/rules.md (Claude never has to read all 118 at once).

Usage:
  python3 scripts/rules.py --topics                 list the topics and their trigger words
  python3 scripts/rules.py 3d voix                  print every rule of these topics
  python3 scripts/rules.py 96 110                   print these rule numbers
  python3 scripts/rules.py --match "téléphone"      print the rules whose text contains a word
Claude picks the topics ITSELF from what the job contains (see references/essentials.md, "Déclencheurs"):
a phone or 3D object in the reference -> 3d ; a voice file -> voix ; a PSD -> visuels ; Studio mode -> studio, etc.
"""
import os as _o, sys as _s; _s.path.insert(0, _o.path.dirname(_o.path.abspath(__file__))); import _mkpy  # noqa: E401,E702,F401  (bon Python + PATH)
import os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES = os.path.join(ROOT, 'references', 'rules.md')

TOPICS = {   # topic: (trigger words, rule numbers)
    'base':       ('toujours', [1, 5, 24, 37, 45, 63, 87, 89, 93, 103, 106, 110, 113, 114, 118, 119]),
    'mesure':     ('mesurer la référence, coupes, fréquences, couleurs', [1, 2, 3, 5, 21, 22, 45, 49, 52, 53, 54, 56, 69, 101]),
    'suivi':      ('élément qui bouge, suivi, écran, étiquette, flou', [4, 6, 7, 8, 28, 46, 55, 66, 68, 80, 96]),
    'texte':      ('textes, phrases, typo, cadre autour d\'un texte, glitch', [15, 60, 73, 97, 98, 106]),
    'voix':       ('voix off, script de voix, alignement, chevauchement', [9, 59, 83, 111, 114, 122]),
    'musique':    ('musique, temps, tempo, rythme, plusieurs références', [10, 11, 12, 35, 37, 85, 107, 108]),
    'storyboard': ('storyboard, validation, preuve côte à côte', [23, 24, 76, 78, 86]),
    '3d':         ('téléphone, objet 3D, logo 3D, icônes qui tournent, Blender', [20, 26, 27, 28, 29, 30, 31, 32, 33, 34, 36, 40,
                   41, 42, 43, 47, 57, 61, 62, 64, 70, 71, 72, 116]),
    'visuels':    ('captures d\'app, PSD, logos de tiers, visuels fournis', [17, 18, 79, 82, 84, 112]),
    'adaptation': ('adapter à la marque, ajouts, écran IA, pub agent IA', [75, 89, 105, 106, 112, 113, 114, 117, 121]),
    'qualite':    ('tremblement, nervosité, zones mortes, effet PowerPoint, rythme mou', [50, 53, 54, 65, 67, 74, 87, 88, 110, 113, 115, 122]),
    'rendu':      ('rendu, assemblage, HD, livraison, durée', [34, 50, 51, 103, 104, 109, 119]),
    'code':       ('pièges JavaScript / GSAP / recettes', [13, 16, 48, 58, 77]),
    'fusion':     ('plusieurs vidéos de référence', [19, 85]),
    'lien':       ('référence donnée par un lien', [81]),
    'installation': ('installation, outil introuvable, mauvais Python', [118, 120]),
    'studio':     ('mode Studio : décalque au pixel près', [90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 104, 105, 108]),
}


def load():
    txt = open(RULES, encoding='utf-8').read().split('\n')
    rules, cur = {}, None
    for line in txt:
        m = re.match(r'^(\d{1,3})\. ', line)
        if m:
            cur = int(m.group(1)); rules[cur] = [line]
        elif line.startswith('#'):
            cur = None
        elif cur is not None:
            rules[cur].append(line)
    return {k: '\n'.join(v).rstrip() for k, v in rules.items()}


def main(argv):
    if not argv or argv[0] in ('-h', '--help'):
        print(__doc__); return 0
    if argv[0] == '--topics':
        for k, (w, ns) in TOPICS.items():
            print(f'{k:11s} {len(ns):2d} règles  ← {w}')
        return 0
    R = load(); want = []
    if argv[0] == '--match':
        word = ' '.join(argv[1:]).lower(); want = [n for n, t in R.items() if word in t.lower()]
    else:
        for a in argv:
            if a.isdigit():
                want.append(int(a))
            elif a in TOPICS:
                want += TOPICS[a][1]
            else:
                print(f'(sujet inconnu : {a} ; voir --topics)', file=sys.stderr)
    seen = []
    for n in want:
        if n not in seen:
            seen.append(n)
    for n in sorted(seen):
        if n in R:
            print(R[n] + '\n')
    print(f'— {len([n for n in seen if n in R])} règle(s) affichée(s)', file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
