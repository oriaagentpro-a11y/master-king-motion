# L'essentiel : à lire avant CHAQUE vidéo (à la place des 119 règles)

Ce fichier suffit pour démarrer. Les règles détaillées de `rules.md` se chargent **à la demande**, sujet par sujet,
avec `python3 scripts/rules.py <sujet>`, quand un déclencheur ci-dessous apparaît. Claude choisit lui-même le mode et les
sujets : l'utilisateur n'a jamais à dire quelles règles appliquer.

## 1. Choisir le mode (automatique, annoncé en une phrase, sans question)

| Mode | Quand | Ce qu'il fait |
|---|---|---|
| **Rapide** (par défaut) | Toute demande du type « la même vidéo pour ma marque », « inspire-toi de cette pub » | Mesure le mouvement de la référence (coupes, durées, eases, positions, rythme) sur les éléments clés, puis construit l'adaptation directement sur ces mesures. Rien n'est deviné, mais on ne reproduit pas la référence au pixel près. |
| **Studio** | L'utilisateur demande une copie exacte (« identique », « au pixel près », « décalque », « reproduction exacte », « côte à côte avec l'original »), OU une scène échoue deux fois aux contrôles du mode Rapide (§ 3) | Décalque complet de la référence en code (SSIM ≥ 0,98 par scène), puis adaptation sur les pistes décalquées. Charger `rules.py studio`. Beaucoup plus long et coûteux. |

La montée en Studio se fait **scène par scène** : on ne décalque que la scène qui résiste, jamais tout le film par réflexe.
Annoncer le mode choisi en une phrase (« Je pars en mode Rapide : mesure du mouvement puis adaptation ») et continuer.

## 2. Déclencheurs : charger les règles costaudes au bon moment

Repérer ces situations dans la demande, la référence ou les fichiers reçus, puis charger le sujet AVANT d'attaquer
l'étape concernée. Plusieurs sujets peuvent se cumuler (`python3 scripts/rules.py 3d voix texte`).

| Situation repérée | Sujet à charger |
|---|---|
| Toujours, au début | `base` |
| On mesure la référence (phase 1) | `mesure`, puis `suivi` dès qu'un élément bouge |
| Un téléphone, un écran en perspective, un objet, un logo ou des icônes en 3D dans la référence | `3d` |
| Des textes animés, des phrases, une typo à respecter | `texte` |
| Un fichier de voix ou un script de voix à écrire | `voix` |
| Une musique, des temps forts, plusieurs références | `musique` (+ `fusion`) |
| Captures d'app, PSD, logos fournis | `visuels` |
| On adapte à la marque, on ajoute des éléments | `adaptation` |
| Storyboard à produire ou à faire valider | `storyboard` |
| Avant le rendu final et avant toute livraison | `qualite`, `rendu` |
| Un bug dans une scène HTML / GSAP | `code` |
| Référence donnée par un lien | `lien` |
| Mode Studio (demandé ou montée automatique) | `studio` |
| Un doute précis | `python3 scripts/rules.py --match "<mot>"` |

## 3. Contrôles qui décident de la montée en exigence (mode Rapide)

Après le storyboard puis après le rendu, lancer les contrôles et réagir sans attendre l'utilisateur :

- `rhythm.py` : doit dire **« identique »** (décalage 0). Sinon, recaler les instants de la scène fautive sur les mesures.
- `style_compare.py` : chaque scène **« conforme »**. Sinon, mesurer plus finement les éléments de cette scène (`rules.py suivi`).
- `nervosity_audit.py` et l'audit de tremblement : aucun saut, aucune zone morte (`rules.py qualite`).
- **Une même scène échoue deux fois → montée en Studio pour cette scène seulement** (`rules.py studio`).

## 4. Les règles de base, en bref (le détail : `rules.py base`)

1. Mesurer avant de construire ; vérifier chaque mesure avant de s'en servir. Une lecture à l'œil se confirme par une mesure.
2. La référence donne le **mouvement**, l'utilisateur donne le **branding** (textes, couleurs, typo, visuels), jamais l'inverse.
3. Tout est recréé en code : rien n'est extrait de la référence (ni image, ni plaque, ni logo de tiers).
4. Une seule horloge pour le minutage ; la voix se cale par segments, coupés sur les silences, sur leur mot clé.
5. Script de voix = une ligne par plan, avec la durée maximale mesurée du plan.
6. Pas de rendu complet sans accord explicite de l'utilisateur sur le storyboard (rendu réel, une image par scène).
7. Typo de la marque, rôle par rôle (titres, textes, prix…).
8. Pas de tremblement : fond stable, pistes lissées, textes au sous-pixel.
9. Jamais d'effet « PowerPoint » : tout bouge, pas d'éléments qui apparaissent puis attendent.
10. Aucune image cassée, aucun aperçu 2D dans le livrable.
11. Chaque nouvelle méthode qui a servi est ajoutée au skill (script + procédure + règle numérotée).
12. L'installation est automatique (`ensure_ready.py`) : ne jamais demander à l'utilisateur d'installer quoi que ce soit.

## 5. Avant un long rendu : prévenir de la durée

- 3D Blender : `python3 scripts/render_estimate.py job.json` mesure une image (carte graphique utilisée si présente)
  et annonce la durée totale. Le dire à l'utilisateur en une phrase, puis lancer le rendu en arrière-plan.
- Film HTML : rendre d'abord 1 s, chronométrer, extrapoler, annoncer.
