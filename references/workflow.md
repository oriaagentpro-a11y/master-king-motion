# Workflow détaillé (commandes)

Chemins : `$MK` = dossier du skill, `$P` = dossier du projet. Toutes les commandes se lancent depuis `$P`.

## 0. Projet
Référence en lien (Pinterest, mp4, m3u8) : `python3 $MK/scripts/fetch_reference.py https://pin.it/xxxx ref/ref1.mp4` (règle 81).

```
python3 $MK/scripts/new_project.py $P --ref ref.mp4 --ref2 ref2.mp4 --music musique.mp3 --voice voix.wav --script script.txt \
        --assets logo.svg capture1.png … --format 16:9
```
Crée `ref/ assets/ analysis/ out/ plan.json notes.json film.html`.

## 1. ADN
```
python3 $MK/scripts/dissect.py ref/ref.mp4 analysis/            # plusieurs refs : analysis/A, analysis/B…
```
Lire : `contact_all.png` (une ligne par scène : début, événements, pic, pause, fin), `curves.png`, `dissect.json`.
Les coupes automatiques sont un point de départ : un volet, un zoom traversant ou un fondu n'est pas une coupe.
→ `notes.json scenes.Sxx.split_at / merge_with`.

Mesurer chaque élément (coordonnées dans la vidéo de référence) :
| Cas | Outil |
| --- | --- |
| forme ou texte clair / foncé, suivi d'une composante | `track_elements.py v t0 t1 out.json [--dark] --thr T` puis `track_fit.py … --pick nearest:x,y` |
| texte d'une couleur, taille et position | `track_textbox.py v f0 f1 x,y,w,h HEX tol tb.json --key nom` |
| carte, bouton, téléphone (4 coins, rotation, perspective) | `track_quad.py v t0 t1 out.json --color HEX --roi …` |
| icône, curseur (gabarit) | `track_template.py` |
| fondu, apparition, clignotement | `track_opacity.py v f0 f1 roi INK BG op.json --key nom` |
| objet 3D, icône, téléphone sur fond uni | `track_mask.py v f0 f1 roi out.json --bg HEX --largest`, puis `track_fit … --curve` (décalque image par image) |
| grilles, lignes fines, cadres | `track_lines.py v f0 f1 out.json --fit ref.mp4 tracks.json --id grille` |
| téléphone / écran / carte en 3D | `track_quad.py v t0 t1 quad.json --color HEX --lines` puis `pose_from_quad.py quad.json ref.mp4 pose.json --fov auto` → `P.setPose(...)` (vrai 3D, `engine/mk-phone3d.js`) |

```
python3 $MK/scripts/track_fit.py tb.json ref/ref.mp4 analysis/tracks.json --id titre --role titre --key titre --props cx,cy,w,h
python3 $MK/scripts/track_fit.py op.json ref/ref.mp4 analysis/tracks.json --id titre --source opacity --key titre --props opacity
```
`track_fit` signale :
- `à décalquer` : une seule courbe ne suffit pas → rejouer la piste avec `RM.trackAt` ;
- `coupé par le cadre` : la fin est extrapolée → confirmer à l'œil ;
- `motif` : mouvement répété → vérifier son ease image par image s'il dure moins de 4 images.

`notes.json` (exemple dans `scripts/dna_build.py`) : type de scène, `transition_in` {type, duration, ease,
source}, typographie {font, weights, case, tracking_em, source}, `elements.X` {slot, kind, patterns / motions
corrigés + source}, finish, rules.
```
python3 $MK/scripts/dna_build.py analysis/ analysis/motion_dna.json
python3 $MK/scripts/dna_check.py analysis/motion_dna.json
```

Fusion de plusieurs références : un ADN par référence, puis
`python3 $MK/scripts/dna_merge.py analysis/motion_dna.json A=analysis/A/motion_dna.json C=analysis/C/motion_dna.json`
(les scènes deviennent A_S01, C_S04… et chacune garde sa vidéo source).

## 2. Plan
`plan.json` : stage, dna, brand {colors, map, fonts}, voice_offset, snap, scenes [{id, ref, vo:[phrases], items,
slots, hold_mode, overlap_out}]. Captures d'app :
```
python3 $MK/scripts/ui_decompose.py assets/ecran.png analysis/ui/ecran --crop-status 0.055 --key-bg
```
→ `overview.png` numéroté et `layers/*.png`. On garde les icônes et illustrations en calques. On réécrit les textes
en HTML et on reconstruit les cartes en HTML, pour animer chaque pièce.

## 3. Son et minutage
```
python3 $MK/scripts/audio_prep.py analysis/audio_plan.json --music assets/musique.mp3 --voice assets/voix.wav --script assets/script.txt --fps 30
python3 $MK/scripts/retime.py plan.json timing.json --audio analysis/audio_plan.json
```
Voix enchaînée (pauses courtes) : ajouter `--align` (transcription locale faster-whisper). Chaque ligne du script est
alors calée sur la voix, avec les mots horodatés : dans le film, `ctx.wordRef(k, j)` donne l'instant où le mot j de la
phrase k est prononcé, pour faire apparaître le mot affiché pile sur le mot dit.
`audio_prep` vérifie la phase des temps (grosse caisse, pas le charleston). Si le nombre de phrases ne correspond pas
au script, ajuster `--min-silence`.

## 4. Film
`film.html` : recettes `RECIPES.Sxx = (ctx) => { …; return { tl, frame? }; }`. API dans `engine/mkm.js` :
- `MK.place(el, cx, cy)`, `MK.fitText(el, {w, size, maxLines})` et `MK.refFontSize(texteRef, hauteurEncre, graisse)`
  pour la mise en page ;
- `MK.split(el, 'char'|'word')` pour les décalages lettre par lettre ou mot par mot ;
- `MK.image`, `MK.color`, `MK.rng` ;
- `ctx.play(tl, el, mouvement)`, `ctx.replay(tl, el, idElement)` et `ctx.motif(id)` pour les mouvements de l'ADN ;
- `ctx.rhythm`, `ctx.voRef(i)` (instant de la phrase i en temps de référence) pour le minutage ;
- `MKPhone3D.create(parent, {W, H, shadow})` (`engine/three-bundle.js` + `engine/mk-phone3d.js`) : **vrai téléphone 3D**
  (Three.js, métal, verre, objectifs, éclairage HDRI `P.hdri('engine/hdri/studio_small_08_2k.hdr')`) :
  - `P.screen` : canvas de l'écran, appeler `P.screenDirty()` après l'avoir dessiné ;
  - `P.card(i, canvas)` : carte 3D qui sort de l'écran ;
  - `P.setPose(pose mesurée)` ou `P.place(cx, cy, h, rx, ry, rz)` pour la position ;
  - `P.render()` dans `frame()` ;
  - modèle `.glb` sous licence avec `{glb: 'assets/phone.glb'}`.
  `mk-phone.js` (CSS) ne sert plus que pour une maquette rapide : jamais quand la référence montre de la vraie 3D.

## 5. Storyboard (validation obligatoire)
```
python3 $MK/scripts/storyboard.py timing.json film.html ref/ref.mp4 out/storyboard
```
Envoyer `out/storyboard/storyboard.png` et le texte de `storyboard.md`. Attendre « OK ».

## 6. Rendu et preuves
```
python3 $MK/scripts/render_film.py film.html out/film_silent.mp4 --timing timing.json --workers 4
python3 $MK/scripts/finalize.py out/film_silent.mp4 out/final.mp4 --music assets/musique.mp3 --voice assets/voix.wav --timing timing.json
python3 $MK/scripts/style_compare.py ref/ref.mp4 out/final.mp4 timing.json out/style --brand-colors
python3 $MK/scripts/polish_lint.py out/final.mp4 --film film.html --timing timing.json --ref ref/ref.mp4
```
Fusion de références : lancer `style_compare` avec chaque référence, en ne lisant que les scènes qui en viennent.
Seuils : rythme ≥ 0,70, événements ≥ 0,75, attaque ≤ 1 image, énergie entre 0,5 et 2, mise en page ≥ 0,70.

## 3D photoréaliste (Blender Cycles)
```
bash $MK/blender/install_blender.sh                       # une fois (Blender 4.2 LTS portable dans blender/app)
# pose mesurée sur la référence
python3 $MK/scripts/track_screen.py ref/A.mp4 323 344 analysis/A/screen_quad.json --dark 105 --debug analysis/A/dbg
python3 $MK/scripts/pose_from_quad.py analysis/A/screen_quad.json ref/A.mp4 analysis/A/pose3d.json --fov auto --id wide
python3 $MK/scripts/pose_refine_edges.py ref/A.mp4 353 403 analysis/A/pose3d.json --anchor 538,40,56 --fovs 8.5 --id closeup --debug dbg
# job (téléphone : spec de segments de pose + cartes) ou export depuis le film (MK.probe)
python3 $MK/scripts/build_3d_job.py p3_3d.json analysis/p3_job.json
python3 $MK/scripts/export_probe.py film.html timing.json P2 logo analysis/p2_job.json --fov 25 --object icon --face face.png
# rendu (images RGBA) puis MK.sequence() dans la recette
$MK/blender/app/blender -b -P $MK/blender/render_job.py -- analysis/p3_job.json
```
Icônes 3D en orbite (pièce, avion, carte, wifi : `blender/tokens_build.py`, décor sur les deux faces) :
```
# la recette publie MK.probe('tokens', [{cx, cy, h, rx, ry, rz} | null, ...]) à chaque image
python3 $MK/scripts/export_probe.py film.html timing.json P2 tokens analysis/p2_tokens_job.json --fov 25 \
        --object tokens --kinds coin_fcfa,plane,card,wifi --out-frames out/render3d/P2_tokens/f_####.png --samples 48
$MK/blender/app/blender -b -P $MK/blender/render_job.py -- analysis/p2_tokens_job.json
```
Objet à pièces mobiles (cadenas : l'anse descend à la fermeture) :
```
# la recette publie MK.probe('lock', { cx, cy, h, rx, ry, rz, shackle })  (rz = -rotation CSS : horaire écran = -Z Blender)
python3 $MK/scripts/export_probe.py film.html timing.json P5 lock analysis/p5_lock_job.json --fov 25 --object padlock \
        --out-frames out/render3d/P5_lock/f_####.png --samples 48
```
La rotation propre d'un jeton est MESURÉE (`silhouette_spin.py`) et liée à l'angle de l'orbite (elle accélère avec
elle) ; les matériaux de téléphone sont vérifiés au zoom pixel (`frame_pairs.py --crop`) avant tout rendu long.
Logo 3D : garder la vue trois-quarts de la référence et sa dérive (ADN `three_quarter`), de face seulement quand la
référence l'est.
Toujours : une image de contrôle (`"still": n` dans le job, `"out"` vers un dossier de test), comparée à la
référence, AVANT le rendu complet ; puis `render_frames` sur les seules images qui changent.

### Enchaîner des rendus Blender en arrière-plan
Lancer les jobs dans UNE seule commande en série (`for job in …; do blender -b … ; done`). Ne jamais attendre la
fin d'un rendu avec `while pgrep -f "<motif>"` : la boucle contient le motif dans sa propre ligne de commande et
s'attend elle-même pour toujours. Pour attendre, tester un fichier de fin (`grep -q MKM_DONE job.log`).

## 7. Passe de vérification image par image
Voir `references/verification.md` (obligatoire à chaque version) : `energy_bars.py`, `frame_pairs.py`
(rejouée / `--raw` / `--crop`), `word_ink.py`, `track_lines.py`, `silhouette_spin.py`, `edge_tilt.py`, `fit_easing.py`.
Une tâche d'arrière-plan qui ATTEND la fin d'une autre consomme sa limite de temps (2 h) pendant l'attente : elle
peut être tuée en plein rendu (cas réel : logo P6 arrêté à 26/30). Mettre tous les rendus d'une même vague dans UNE
chaîne en série, ou lancer chaque attente juste avant son tour ; après un arrêt, relancer seulement les images
manquantes (`render_frames`) en gardant toutes les clés du job.
Pour savoir ce qui tourne VRAIMENT : `ps -eo pid,etime,args | grep "[b]lender/app/blender" | grep -v "bash -c"`
(`pgrep -af "blender -b"` liste aussi les commandes d'attente qui contiennent ce texte : faux positifs). Une attente
sur le journal d'un rendu qui ne démarrera jamais bloque toute la file : vérifier l'état réel avant d'attendre.

## 8. Proposer « notre plus » (après une première version fidèle)
```
python3 $MK/scripts/nervosity_audit.py timing.json out/compare/reference_recalee.mp4 out/film_silent.mp4 --json out/compare/nervosity.json
python3 $MK/scripts/additions_board.py out/film_silent.mp4 storyboard_v3/additions.json storyboard_v3/storyboard_plus.png --font assets/Brand.ttf
```
La planche montre, par scène, l'image actuelle et les ajouts avec leur mouvement décrit (règle 75), en RENDU RÉEL
(règle 76) :
```
python3 $MK/scripts/project_points.py analysis/p3_job.json analysis/p3_points.js --var P3PTS --points c0:-0.18,0,0:card=0 c1:-0.18,0,0:card=1
python3 $MK/scripts/render_film.py film.html x.mp4 --timing timing.json --stills out/sb_base --frames 50,180,240
python3 $MK/scripts/render_film.py film.html x.mp4 --timing timing.json --stills out/sb_plus --frames 50,180,240 --query plus=1
python3 $MK/scripts/additions_board.py out/film_silent.mp4 additions.json storyboard_plus.png --base out/sb_base --plus out/sb_plus
```
Validation de l'utilisateur, puis construction dans les recettes (valeurs dans l'ADN avec la mention « ajout validé »).

## 9. Avant la livraison : storyboard général
```
python3 $MK/scripts/general_storyboard.py out/final.mp4 timing.json storyboard/general.json storyboard/storyboard_general.png --font assets/Brand.ttf
```
