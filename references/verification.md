# Passe de vérification image par image (obligatoire avant toute livraison)

Un score global ne prouve rien. Chaque défaut de la vidéo MTN MoMo (cas réel du skill) a été trouvé par cette passe,
pas par les scores. On la refait **à chaque version**, scène par scène, dans cet ordre. Rien n'est sauté, rien n'est
« à peu près » : chaque écart est corrigé ou expliqué par écrit (raison mesurée).

`$MK` = dossier du skill. Les commandes se lancent depuis le dossier du projet.

## 0. Avant de mesurer : la référence est-elle saine ?
```
python3 -c "import sys; sys.path.insert(0,'$MK/scripts'); import mkcommon as mk; print(mk.pulldown('ref/A.mp4'))"
```
- Une référence convertie (25 → 30 i/s) répète une image sur six. Si `pulldown` renvoie une période : toute mesure se
  fait sur les **images distinctes** (les outils du skill le font seuls), `dna_build` retire ces images des tables,
  `build_3d_job` rééchantillonne les poses. Une valeur lue à l'œil sur une image dupliquée est fausse (règle 52).
- Vérifier une image suspecte : écart moyen avec la précédente (0,7 = copie ; 8-16 = vraie image).

## 1. Où ça diffère : les courbes
```
python3 $MK/scripts/style_compare.py ref/A.mp4 out/film_silent.mp4 timing.json out/compare --brand-colors
python3 $MK/scripts/energy_bars.py out/compare/reference_recalee.mp4 out/film_silent.mp4 <f0> <f1> --holes
```
- `style_compare` lit la référence de chaque scène (`source`) : une seule passe suffit pour plusieurs références.
- `energy_bars` : barres d'énergie réf. | nous, image par image. On y voit un mouvement absent (réf. qui bouge, nous
  plat), en avance, trop lent, et les **trous** (énergie ~0 entre deux images qui bougent) : dans la référence =
  images dupliquées ; dans notre film = un arrêt à corriger.

## 2. Ce qui diffère : les planches de paires
```
python3 $MK/scripts/frame_pairs.py timing.json out/film_silent.mp4 out/p.png 300 305 309 313            # rejouée
python3 $MK/scripts/frame_pairs.py timing.json out/film_silent.mp4 out/p.png 300 305 309 313 --raw      # brute
python3 $MK/scripts/frame_pairs.py timing.json out/film_silent.mp4 out/z.png 296 --raw --crop 860,0,1560,420 --width 640
```
- **Rejouée** : la référence sur notre horloge. Une image en double (fantôme) peut n'être qu'un mélange de deux
  images du rejeu : confirmer avec `--raw`, qui montre l'image source sans mélange.
- **Zoom pixel** (`--crop`) : contour d'un téléphone, îlot caméra, bord d'un texte, détail d'une icône. C'est ainsi
  qu'on a vu la bande blanche autour de l'écran et l'îlot blanc (règle 57).
- Toujours regarder **les fins de scène** jusqu'à l'image avant la coupe : la plupart des gestes manquants étaient
  des sorties (groupe qui monte, téléphone qui glisse, mot qui rétrécit, grille qui explose) (règle 53).
- Toujours regarder **l'angle de vue des objets 3D** : un objet qui revient de face « par défaut » paraît figé alors
  que la référence le garde en trois-quarts qui dérive (règle 61).

## 3. Mesurer ce qu'on a vu (jamais l'œil seul)
| Ce qu'on voit | Outil | Ce qu'on en tire |
|---|---|---|
| un mot qui arrive / repart, une couleur d'accent, un texte brouillé | `word_ink.py ref f0 f1 --band y0,y1` | décalage de départ (px / hauteur), durée en images distinctes, contraste = opacité, saturation = accent |
| une ligne, une grille, un cadre | `track_lines.py ref f0 f1 out.json --bg HEX --tol 6 --min-cover 0.15` | position de chaque ligne **jusqu'à sa sortie du cadre** |
| un objet qui tourne sur lui-même | `silhouette_spin.py ref f0 f1 --hsv h0,h1,s,v --near x,y` | rapport des axes (1 de face, ~0 de profil) → vitesse en °/s |
| un objet qui penche | `edge_tilt.py ref f0 f1 --fit t0` | inclinaison signée (horaire > 0) et son ease |
| un objet qui monte, glisse, grossit | `track_template.py`, `track_elements.py`, ou `cv2.matchTemplate` sur un gabarit | position / taille par image distincte |
| une taille réelle (objet plus petit que la réf.) | boîte de l'objet à plusieurs seuils (60, 100, 140) | le cœur de l'objet (seuil haut) sépare échelle et halo de flou |
| l'instant exact d'un geste rapide | planche des images **brutes** autour du geste | image de début / de fin (une fermeture d'anse lue 6 images trop tôt à l'œil) |

Puis `fit_easing.py` sur la série (temps = vraies secondes des images distinctes). Règles :
- mesurer **jusqu'à la dernière image avant la coupe** ; un ajustement arrêté avant est tronqué (ex. `power1.inOut`
  vers 487 px au lieu de `power2.in` vers 186 px) ;
- si l'ajustement libre dérive (départ avant le geste, valeur de départ absurde), fixer le départ connu et vérifier
  3 points à la main ;
- si deux gestes se chevauchent dans la référence, garder leur **décalage mesuré** (règle 54).

## 4. Écrire la mesure, puis le code
- Chaque valeur va dans l'ADN **et** dans `notes.json` avec sa source (images, outil, rmse). Une ancienne valeur fausse
  est remplacée, et la note dit pourquoi (« œil −12° mauvais sens → mesuré +6,7° »).
- Dans la recette, respecter les **deux horloges** (règle 58) : timeline et `tr` = temps de la référence ; `tn` =
  nouveau temps, celui de la voix. Un geste de la référence placé dans un passage étiré se joue en temps réel sur
  `tn`, ancré sur le mot dit (règle 59). Une sortie se cale sur notre coupe (`toCut`).
- Un élément qui épouse un contenu (cadre autour d'un texte) se règle sur **notre** contenu (règle 60).
- Texte brouillé : `MK.scramble(texte, q, graine)` ; mots qui montent : décalage + opacité mesurés, sur `tn`.

## 5. Vérifier avant de rendre long
```
python3 $MK/scripts/render_film.py film.html x.mp4 --timing timing.json --stills out/st --frames 60,63,66,69,72 --query r3d=0
```
- Images fixes de la scène corrigée, comparées à la planche de référence.
- 3D : une image de contrôle (`"still": n` dans le job, sortie dans un dossier de test), comparée au **zoom pixel**,
  AVANT le rendu complet. Puis ne re-rendre que les images qui changent (`render_frames`, poses comparées), toutes
  les clés gardées pour le flou de mouvement (règle 50).
- Enchaîner les rendus Blender en série, l'attente sur `MKM_DONE` dans le journal, jamais `pgrep` (workflow).

## 5 bis. Avant chaque rendu 3D
```
python3 $MK/scripts/pose_audit.py analysis/p2_job.json --first-frame 92 --allow 140-205
```
« poses : OK » obligatoire (règle 71). Puis une image de contrôle à 2 instants (lisibilité, couleurs, angle).
Un effet sur un texte : regarder la planche image par image ET la vidéo à vitesse normale (règle 73).

## 6. Recommencer la passe
Rendu complet → `style_compare` → `energy_bars --holes` → planches de chaque scène → mixage → `polish_lint`
(polices déclarées, son, loudness). Rapport : par scène, ce qui est conforme, ce qui reste en écart et sa raison
**mesurée** (ex. « P4 : les mots suivent la voix, plus lente que celle de la référence — voulu »).

## 7. Ce que la passe a trouvé sur le cas réel (à chercher en premier ailleurs)
1. Référence 25 → 30 i/s : faux arrêts dans les mesures et dans nos objets 3D (règle 52).
2. Sorties de scène absentes ou tronquées (règle 53) ; gestes enchaînés au lieu de se chevaucher (54).
3. Suivi 3D figé par un `clamp` quand le flou casse le suivi (55).
4. Lectures à l'œil fausses : sens d'une rotation, instant d'une fermeture, taille d'un objet (56).
5. Téléphone : vitre et îlot vernis miroir → contour et îlot blancs (57).
6. Horloges mélangées, gestes ralentis par l'étirement → vidéo « standard », sans nervosité (58, 59).
7. Cadre de grille réglé sur les pixels de la référence au lieu de notre texte (60).
8. Objets 3D revenus de face, icônes 2D tournées en CSS → figé et bancal (61, 62).
9. Image cassée d'une séquence 3D pas encore rendue ; aperçu 2D pris pour le résultat (51).
10. Arrêt d'une image dans notre film : table de mesures qui s'arrête une image avant l'événement suivant (65).
11. Objets fournis en image : à modéliser en 3D avec leurs pièces mobiles (64).
12. Pose 3D figée avant le premier suivi fiable : prolonger le mouvement mesuré (66).
13. Zone morte entre deux mots / événements : ce qui bouge en continu dans la référence (cadre, mot qui se pose) (67).
14. Logo 3D penché et immobile, saut à l'effondrement (71, 72).
15. Texte brouillé illisible et clignotant (73).

Confirmer tout « trou » d'énergie par l'écart de pixels entre images consécutives (artefact possible sur des
lignes très fines) avant de le corriger.
