---
name: master-king-motion
description: Produit une vidéo motion design de niveau studio inspirée AU DÉTAIL PRÈS d'une ou plusieurs vidéos de référence, mais avec le contenu de l'utilisateur (textes, logo, captures d'app, couleurs, musique, voix off). Mesure l'ADN de la référence (rythme, eases, durées, transitions, typo, palette, finition), l'applique au nouveau contenu, cale tout sur la voix off et la musique, fait valider un storyboard, puis prouve la ressemblance par des mesures de style. À utiliser dès que l'utilisateur fournit une vidéo d'inspiration et veut « la même chose pour ma marque / mon app / mon produit », une pub, un lancement, une promo d'application, une vidéo motion 16:9 ou verticale.
---

# Master King Motion

Objectif : une vidéo qu'on ne peut pas distinguer du travail d'un studio. Elle reprend la référence au détail
près (vitesses, eases, rythme, transitions, composition, finition), mais avec le contenu de l'utilisateur.
Rien n'est « à peu près » : chaque valeur vient d'une mesure sur la référence ou d'un contrôle à l'œil noté.

Outils : `scripts/` (Python), `engine/` (rendu Chromium + GSAP), `templates/film.html`.
**Avant CHAQUE vidéo, lire `references/essentials.md`** (court) : choix AUTOMATIQUE du mode (Rapide par défaut,
Studio si copie exacte demandée ou si une scène résiste aux contrôles), déclencheurs et règles de base. Les 124 règles
d'or de `references/rules.md` ne se lisent PAS en entier : Claude charge lui-même les sujets utiles au moment où ils
servent, avec `python3 scripts/rules.py <sujet>` (`--topics` pour la liste : 3d, voix, texte, suivi, studio…).
L'utilisateur n'a jamais à dire quelles règles appliquer. Commandes : `references/workflow.md` ; qualité :
`references/doctrine.md` ; passe image par image avant livraison : `references/verification.md`.
Chaque nouvelle méthode qui a permis d'atteindre le résultat est AJOUTÉE au skill AU MOMENT où elle sert (script +
procédure + règle numérotée + sujet dans `scripts/rules.py`). `references/reverse-motion-METHODS.md` contient la
mémoire technique des mesures (pièges P1–P27).

## Valeurs par défaut (ne pas demander)

- **Format 16:9, 1920×1080, 30 i/s**, sauf si l'utilisateur demande autre chose, même à demi-mot (« pour TikTok »,
  « en story », « pour Reels », « vertical » → 9:16 1080×1920 ; « carré » → 1:1 ; « post Instagram » → 4:5).
- **Voix off : Claude peut la générer lui-même** avec `scripts/voix_off.py` (moteur VoxStudio Pro, API Gemini TTS,
  clé Google AI Studio de l'utilisateur, demandée à la première génération : règle 124). Il écrit le script une ligne
  par plan, le fait valider, génère une réplique par fichier, vérifie par retranscription, puis cale. Si l'utilisateur
  préfère sa propre voix, il fournit son fichier. **Musique : fournie par l'utilisateur** (bibliothèque libre de droits) ;
  à défaut, on propose une direction musicale et on attend son fichier.
- Effets sonores seulement si la référence en a, ou sur demande (`sfx.py`).


## Deux modes (choisis automatiquement, voir `references/essentials.md`)

**Mode Rapide (par défaut)** : phases 0 à 6 ci-dessous ; la phase 1 mesure le mouvement des éléments clés
(coupes, durées, eases, positions, rythme) sans décalque au pixel. Contrôles `rhythm.py` « identique »,
`style_compare.py` « conforme », `nervosity_audit.py` ; une scène qui échoue deux fois monte en Studio, seule.

**Mode Studio** (copie exacte demandée, ou montée automatique d'une scène) : pipeline imposé ci-dessous
(règles 90 à 94, `python3 scripts/rules.py studio`).

## Pipeline du mode Studio (règles 90 à 94)
1. Décalque mesuré de la référence (SSIM ≥ 0,98 visé par scène, 0 texte en double) — TOUT recréé en code, rien
   d'extrait (règle 93) ; jusqu'à 2 sous-agents armés de toute la méthode (règle 92).
2. Contrôle final du décalque et rapport.
3. Script de voix écrit sur le rythme de la référence, fourni à l'utilisateur pour qu'il génère sa voix (règle 94).
4. Prompts intégraux pour les images / vidéos réelles nécessaires.
5. Storyboard de l'adaptation en rendu réel → validation.
6. Rendu final sur les pistes du décalque + mixage + `rhythm.py` identique.

Outils du décalque (règles 95 à 99) : textes `scripts/wordfit/` ; phrases = vraie ligne ajustée par synthèse (98) ;
surfaces suivies = `homography_track.py` → `rectify_median.py` (planche médiane hors occultations) →
`homography_refine.py` (ECC sur la planche) → `vectorize_image.py --image … --layered` (96) ; faces d'étiquettes
`--drop-light` + texte en vraie police (97) ; sorties en profondeur = échelle par couche + défocalisation (99).

## Les 7 phases (dans l'ordre, sans en sauter)

0. **Installation automatique (Claude la fait lui-même, sans rien demander à l'utilisateur)** : au début de CHAQUE
   travail, lancer `python3 scripts/ensure_ready.py` depuis le dossier du skill (sous Windows : `python`). S'il
   affiche « PRÊT », continuer. Sinon il installe tout ce qui manque, une seule fois : Node.js, Python, FFmpeg, git,
   modules Node (GSAP, Three.js, Playwright), Chromium, modules Python, modèle de transcription de la voix et
   Blender 4.2 LTS (dans `blender/app/`), puis un rendu de test. Lancer la commande avec un long délai
   (≈ 20 min) ou en arrière-plan. Ne JAMAIS demander à l'utilisateur d'installer quoi que ce soit lui-même ;
   seul un mot de passe administrateur (sudo) peut lui être demandé si le système l'exige.
   Projet : `python3 scripts/new_project.py <dossier> --ref ref.mp4 [--ref2 …] --music … --voice … --format 16:9`.

1. **Disséquer et mesurer la référence** (mode Rapide : dissection + mesure des éléments clés ; mode Studio : décalque reverse-motion mesuré AVANT toute adaptation, règle 90, SSIM ≥ 0,98 par image, 0 fantôme). Charger `rules.py mesure suivi` (+ `3d`, `texte`… selon ce que montre la référence).
   - `dissect.py ref.mp4 analysis/` : coupes, scènes, palette et rôles, mise en page, énergie de mouvement,
     événements, pauses, flou de mouvement, grain, vignettage, tempo. **Regarder** `contact_all.png` et `curves.png`.
   - Mesurer chaque élément qui bouge : `track_elements.py` / `track_textbox.py` / `track_quad.py` /
     `track_template.py` / `track_opacity.py`, puis `track_fit.py` (ease GSAP, départ, durée, valeurs normalisées,
     dépassement, motif répété).
   - Écrire `analysis/notes.json` : ce que seul l'œil voit (type de scène, transitions, typo, règles de style,
     corrections des mesures trop grossières avec leur source). Scènes à découper ou fusionner : `split_at` / `merge_with`.
   - `dna_build.py analysis/ analysis/motion_dna.json`, puis `dna_check.py` doit dire « ADN valide ».
   - Plusieurs références : un ADN par référence. Le plan dit quelle scène vient de quelle référence (mode fusion).

2. **Plan de contenu** : `plan.json`. On associe chaque scène de la référence à un emplacement de contenu de
   l'utilisateur, avec la palette de marque (`brand.map` : couleur de la référence → couleur de la marque, pour garder
   le rythme clair / sombre / accent), les polices et les phrases de la voix.
   - Une scène de référence peut être réutilisée (plus de contenu) ou sautée. Une scène rythmique prend `items`.
   - Manque un visuel (objet 3D, décor, rendu de téléphone, illustration) ? Écrire les **prompts** pour l'outil de
     génération de l'utilisateur (`references/assets-prompts.md`) et attendre ses fichiers. Ne jamais inventer un
     visuel bâclé à la place.
   - Captures d'app : `ui_decompose.py` (blocs, icônes, libellés en calques), puis reconstruction en HTML (texte vivant
     dans la police de marque, icônes en calques). Les écrans vont dans le téléphone en code (`engine/mk-phone.js`).
     Remplacer toute donnée personnelle visible (noms, numéros, soldes réels) par des valeurs fictives.
   - Design fourni en PSD (affiche, visuel) : `psd_decompose.py` → `psd_rebuild.py` → `psd_compare.py` (règles 82 et
     84) : l'affiche est recomposée en code à l'identique (textes vivants, effets refaits) et prouvée contre le PSD
     AVANT d'être animée ; le film anime les éléments `#L<index>` de cette recomposition.

3. **Caler sur le son** : `audio_prep.py` (temps de la musique, phrases de la voix off, script ligne à ligne),
   puis `retime.py plan.json timing.json --audio analysis/audio_plan.json`.
   - Les entrées et sorties gardent leur vitesse mesurée.
   - Seule la pause est étirée. Une pause trop longue est jouée à vitesse normale puis coupée, jamais accélérée.
   - Un mouvement continu (barre, zoom lent) garde sa proportion.
   - Une scène rythmique passe au tempo de la nouvelle musique.
   - Lire chaque `ATTENTION` : chacune est tranchée avant le storyboard.

4. **Construire le film** (`film.html`) : une recette par scène de référence, en secondes locales de la
   référence. Les valeurs viennent de l'ADN (`ctx.replay`, `ctx.play`, `ctx.motions`, `ctx.motif`, `ctx.rhythm`,
   `ctx.dna.transition_in`). Le contenu vient de `ctx.slots`, les couleurs de `ctx.colors` / `MK.color()`, la taille
   des textes de `MK.refFontSize()` (échelle typographique de la référence).
   - Une recette est une fonction **non async** qui renvoie `{ tl }`, plus `frame(tn)` pour les mouvements à
     vitesse constante (rotation, dérive).
   - `dna_check.py ADN --film film.html` : aucun ease inventé.

5. **Storyboard → VALIDATION DE L'UTILISATEUR (obligatoire)**
   - `storyboard.py timing.json film.html ref.mp4 out/storyboard` : pour chaque scène, référence | nouvelle vidéo
     aux mêmes instants, plus le minutage, la voix off, le contenu et les points à trancher.
   - Envoyer `storyboard.png` et `storyboard.md` à l'utilisateur et **attendre son accord explicite**. Pas de
     rendu complet avant. Chaque remarque → plan, recette ou minutage corrigé → nouveau storyboard.

6. **Rendu, mixage, preuves**
   - `render_film.py film.html out/film_silent.mp4 --timing timing.json`
   - `finalize.py out/film_silent.mp4 out/final.mp4 --music … --voice … --timing timing.json` (voix nette, musique
     baissée sous la voix, -14 LUFS, H.264 haute qualité)
   - `style_compare.py ref.mp4 out/final.mp4 timing.json out/style [--brand-colors]` : la référence est rejouée sur la
     nouvelle horloge, puis on compare rythme, événements, attaque, énergie, mise en page, lumière, netteté et grain,
     scène par scène. **Regarder `side_by_side.mp4` en entier.**
   - `polish_lint.py out/final.mp4 --film film.html --timing timing.json --ref ref.mp4` : format, son = image,
     loudness, images figées, pops, scintillement, marges, déterminisme du code.
   - **Passe de vérification image par image (obligatoire, `references/verification.md`)** : `energy_bars.py`
     (où ça diffère), `frame_pairs.py` rejouée / `--raw` / `--crop` zoom pixel (ce qui diffère, fins de scène, angle
     des objets 3D), puis mesure de chaque écart (`word_ink.py`, `track_lines.py`, `silhouette_spin.py`,
     `edge_tilt.py`, gabarits) et `fit_easing.py` jusqu'à la coupe. Avant tout rendu 3D : `pose_audit.py` (règle 71). Chaque mesure → ADN + `notes.json` avec sa source.
   - Corriger puis recommencer jusqu'à : `dna_check` valide, `polish_lint` sans bloquant, et chaque test de
     `style_compare` en échec **corrigé ou expliqué** (ex. un texte plus long que celui de la référence change la mise
     en page). Un score n'est jamais une preuve à lui seul.

7. **Livrer** : `final.mp4`, `side_by_side.mp4`, et un rapport court : scènes et références utilisées, police,
   scores par scène, écarts restants et leur raison, ce qui vient de visuels générés par l'utilisateur.

## Règles absolues

- Mesurer avant de construire. Aucun ease, aucune durée, aucune position tapés « à l'œil » sans source dans `notes.json`.
- Interdits : `Math.random`, `Date.now`, `requestAnimationFrame`, transitions et animations CSS, `repeat: -1`.
  Tout est une fonction du temps (utiliser `MK.rng(graine)`).
- Vraies polices chargées (fichier de marque, ou la police Google la plus proche via `font_search.py`, nommée dans le rapport).
- Finition de la référence reproduite avec SES valeurs (grain, flou de mouvement, vignettage), et rien de plus.
- Ce que le code ne sait pas recréer (rendu 3D photoréaliste, prise de vue réelle) : visuel fourni par
  l'utilisateur (prompts), intégré et animé dans le style mesuré. Dit dans le rapport.
- Droits : on reprend une recette (rythme, style), pas une œuvre. Pas de logo, de personnage ni de plan copié d'une
  autre marque. Les éléments de la marque de l'utilisateur viennent de lui.
- Toujours dire ce qui a été vérifié et ce qui ne l'a pas été.
- Toute 3D de la référence (téléphone, produit, logo, icônes en orbite) se fait en vraie 3D photoréaliste avec
  **Blender Cycles** (`blender/` : `phone_build.py`, `icon_build.py`, `tokens_build.py`, `render_job.py`), avec la
  pose mesurée image par image (`pose_from_quad.py`, `pose_refine_edges.py`) ou exportée du film (`export_probe.py`),
  jamais un aplat ni une image 2D tournée en CSS (règles 20, 26-62). Three.js (`mk-phone3d.js`) sert d'aperçu rapide.
- **Chaque méthode qui sert est enregistrée DANS le skill au moment où elle sert, pas à la fin** : un script
  réutilisable dans `scripts/` (avec son usage en tête de fichier), la procédure dans `references/verification.md`
  ou `references/workflow.md`, et une règle numérotée avec le cas réel dans `references/rules.md`. Le skill est
  partagé : un autre Claude doit pouvoir refaire exactement le même travail en suivant les fichiers, sans cette
  conversation. Un outil de travail laissé dans un dossier temporaire est une méthode perdue.
