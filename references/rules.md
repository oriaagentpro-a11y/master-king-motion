# Règles d'or : méthodes obligatoires (à ne jamais ignorer)

Chaque règle vient d'un problème réel, rencontré et corrigé sur un projet. Lire ce fichier **avant chaque vidéo**.
Quand une nouvelle méthode permet d'atteindre le résultat, l'ajouter ici (numéro suivant, avec le cas qui l'a rendue
nécessaire). Une règle ne s'enlève jamais. Si elle doit changer, la nouvelle version la remplace, avec sa raison.

## A. Observer et mesurer
1. **Mesurer avant de construire.** Chaque position, durée, courbe et couleur du film a une source : une mesure
   (`track_*`, `fit`) ou une lecture à l'œil notée dans `notes.json` avec les images concernées (« œil f412-f422 »).
   Une valeur sans source est refusée.
2. **Image par image sur chaque scène reprise.** Planche dense horodatée (0,1 à 0,25 s entre images), puis recadrage
   image par image de chaque transition, chaque apparition de texte et chaque objet qui bouge (`ffmpeg select=between(n,a,b)` + `tile`).
   La planche de `dissect.py` ne suffit jamais. (MTN : les mots de l'intro A n'apparaissent pas en fondu, ils
   grossissent en 2 images, invisible à 0,25 s.)
3. **Les coupes automatiques ne sont qu'un point de départ.** Un volet, un zoom traversant ou un fondu n'est pas une
   coupe. Découper ou fusionner (`split_at`, `merge_with`) après avoir regardé.
4. **Un mouvement complexe se décalque.** Rotation 3D, rebond, objet qui grossit en tournant, trajectoire irrégulière :
   on n'ajuste pas une seule courbe. On mesure la courbe image par image (`track_mask` + `track_fit --curve`) et on la
   rejoue avec `MK.curveAt`. Une seule courbe GSAP seulement si `track_fit` dit `ok`.
5. **Vérifier chaque mesure avant de l'utiliser.** Un masque capte aussi la grille, le texte, un fond en dégradé, ou
   l'image de raccord du plan précédent. Regarder la courbe, puis :
   - rejeter les images de raccord (borner le temps de lecture, ex. `max(411/30, t)`) ;
   - restreindre la zone mesurée ;
   - ou repasser à l'œil, en le notant.
   (MTN : la courbe de l'icône de fin était fausse, remplacée par une lecture image par image notée.)
6. **Grilles et lignes fines : `track_lines.py`.** Segmenter les phases explicitement (ouverture, recadrage, zoom),
   une courbe par phase. Ne pas laisser un découpage automatique fusionner des mouvements distincts.
7. **Bord ou centre ?** Noter si une valeur mesurée est un bord ou un centre (`left`/`cx`). (MTN : le bord droit du
   téléphone pris pour son centre l'avait poussé hors cadre.)
8. **Formes fines** (étoile, filets, icônes au trait) : les dessiner en segments fins et comparer au recadrage de la
   référence. Une courbe de Bézier quadratique gonfle les branches vers le centre.

## B. Son et minutage
9. **Voix enchaînée → `audio_prep.py --align`.** Chaque ligne du script est calée sur la voix, avec les mots horodatés.
   Tout texte qui reprend la voix apparaît **sur le mot prononcé** (`ctx.wordRef`). Une animation de la référence
   synchronisée sur un mot garde son décalage mesuré par rapport à ce mot (ex. recadrage 0,367 s avant le mot).
10. **Phase des temps musicaux** : vérifier la grosse caisse (basses), pas le charleston (`audio_prep` le corrige).
    Les coupes tombent sur les temps de la musique de l'utilisateur.
11. **On ne fait jamais accélérer une pause.**
    - Pause plus longue que dans la référence : on l'étire.
    - Pause plus courte : on la joue à vitesse normale, puis on coupe la fin.
    - Mouvement continu (barre de progression, zoom lent) : il garde sa proportion.
    - Mouvement à vitesse constante (rotation, dérive, défilement) : il suit le temps réel de la nouvelle vidéo, dans `frame(tn)`.
12. **Scène rythmique** (un élément par temps) : autant d'éléments que de contenu, à l'intervalle de la référence
    recalé sur le tempo de la nouvelle musique.

## C. Construire le film
13. **Recette = fonction non async qui renvoie `{ tl }`.** Une timeline GSAP est un « thenable » : renvoyée depuis une
    fonction `async`, elle bloque le rendu pour toujours.
14. Les erreurs du film doivent remonter (`window.__mk_error`), jamais un écran qui attend en silence.
15. **Texte** :
    - la taille vient de l'échelle de la référence (`MK.refFontSize` sur un mot de référence et sa hauteur mesurée) ;
    - après ajustement, l'élément épouse son texte (`fitText`), pour que le centrage soit juste ;
    - un texte plus long que l'original rétrécit dans SA boîte.
16. **Textures locales en WebGL** : Chromium doit avoir `--allow-file-access-from-files`. Sinon la texture est
    « contaminée » et le rendu échoue. C'est intégré à `render.mjs` et `rmcommon.py`.
17. **Visuels fournis par l'utilisateur : toujours découpés en calques animables.**
    - Planche d'objets : composantes alpha séparées (`icone_*.png`).
    - Objet en plusieurs pièces (cadenas : anse et corps) : découpe géométrique quand la couleur trompe (reflets),
      puis nettoyage des débordements.
    - Vérifier chaque calque sur fond sombre avant de l'utiliser.
18. **Captures d'app** : décomposer (`ui_decompose.py`), reconstruire en HTML ce qui doit bouger, et remplacer toute
    donnée personnelle (nom, numéro, solde, heure : 9:41) par des valeurs fictives.
19. **Fusion de références** : un ADN par référence, puis `dna_merge.py`. Chaque scène garde sa vidéo source pour le
    storyboard et la comparaison.
20. **Vrai 3D quand la référence montre de la 3D** (téléphone, objet produit), jamais un aplat CSS qui imite.
    - Le moteur est `engine/mk-phone3d.js` (Three.js, matières physiques, éclairage d'environnement, écran en
      texture vivante, cartes 3D qui sortent réellement de l'écran).
    - La pose (position, distance, rotations X/Y/Z) est **mesurée image par image** sur la référence : 4 coins de
      l'écran (`track_quad.py`), puis `pose_from_quad.py` (solvePnP).
    - Quand l'écran n'est pas visible (le téléphone de dos), on mesure la silhouette, puis on assure la continuité.
    - Modèle `.glb` sous licence si l'utilisateur en fournit un. Éclairage HDRI de studio pour le photoréalisme.

20b. **Coins d'un écran ou d'une carte à coins arrondis = intersection de 4 droites ajustées sur les bords**
    (`track_quad.py --lines`), jamais les points extrêmes ou l'enveloppe convexe. Mesuré sur rendu de contrôle : les
    points extrêmes faussent la pose 3D de 5 à 8° ; les droites ajustées la retrouvent à 0,3° près (0,2 px de
    reprojection).
20c. **Valider un outil de mesure 3D par un aller-retour** avant de s'y fier : rendre une pose connue, la mesurer,
    comparer. Un outil non validé ne pilote pas le film.

## D. Vérifier
21. **Comparer sur la même horloge** : la référence est rejouée sur le minutage de la nouvelle vidéo
    (`reference_recalee.mp4`), puis on compare image pour image.
22. **Fréquences d'images différentes** (25 / 30 / 60 i/s) : rééchantillonner par fondu entre images voisines. Une
    image dupliquée crée un faux « zéro mouvement » qui ruine la corrélation.
23. **Auto-revue du storyboard avant de l'envoyer.** Comparer chaque paire référence / nouveau. Tout écart visible
    (épaisseur, taille, position, couleur, forme) est corrigé avant envoi. Les images clés ne tombent jamais sur une coupe.
24. **Pas de rendu complet sans accord explicite de l'utilisateur sur le storyboard.**
25. Un score n'est jamais une preuve : regarder la vidéo côte à côte en entier, puis chaque transition image par image.

## E. 3D photoréaliste (téléphone, produit, objet)
26. **Réalisme irréprochable = Blender Cycles**, installé par le skill (`bash blender/install_blender.sh`).
    - Le téléphone est modélisé au détail près par `blender/phone_build.py` : coins continus, tranche métal chanfreinée,
      bandes d'antenne, boutons en creux, USB-C, grilles, île dynamique, dos dépoli, plateau caméra poli, objectifs
      (bague, cellule, verre traité), flash.
    - Vue colorimétrique `Standard` (AgX ou Filmic désaturent les couleurs de marque), éclairage HDRI de studio.
    - La 3D WebGL (`mk-phone3d.js`) ne sert qu'à prévisualiser.
27. **La focale de la référence se mesure et se respecte.** `pose_from_quad.py --fov auto` (cas MTN : 8,5°,
    téléobjectif de plan produit, confirmé indépendamment sur 2 plans). Une caméra 3D à une autre focale trahit la copie
    par sa perspective.
28. **Mesurer la pose selon ce qui est visible.**
    - Écran entier : `track_screen.py` (le trou clair dans la bordure sombre ; régler `--dark` sur la vraie bordure),
      puis `pose_from_quad.py`.
    - Écran coupé par le cadre : match-move sur les contours, `pose_refine_edges.py`, initialisé par une **ancre lue
      à l'œil** sur un zoom quadrillé (centre et largeur de l'île), puis suivi image par image.
    - Images floues ou trop rapides (pivot, raccord) : poses clés à l'œil, notées avec leurs numéros d'image.
29. **Toute pose mesurée se valide en projetant le contour 3D sur la référence** (overlays `--debug`). Une pose qui ne
    colle pas est rejetée, quel que soit son score. (MTN : la pose tirée d'une petite carte d'UI, 1,9 px d'erreur,
    était fausse à la projection ; le match-move sur les contours est juste, 2,4 px.)
30. **Petite surface plane** : ambiguïté IPPE (deux poses miroir), résolue par la continuité temporelle. Les
    mouvements lents se lissent par un polynôme (`--poly 2`).
31. **La mise en scène autour de l'objet se mesure aussi.** Panneau incrusté (marge `expo.out` 1,1 s), objet qui
    déborde du panneau par le haut, sortie du panneau : reproduits par détourage (`clip-path`).
32. **Les éléments d'UI qui bougent en 3D sont de vrais objets** : épaisseur, tranche, dos (cartes de A :
    tranche argent, dos noir satiné). Leurs gestes sont calculés en temps réel par `build_3d_job.py` et calés sur
    les mots dits.
33. **Matières comparées à la référence, image contre image.**
    - Vernis d'écran léger (un vernis plein reflète le studio et délave les couleurs).
    - Dos de carte satiné (un noir miroir renvoie l'écran à l'envers).
    - Flou de mouvement proportionné : obturateur 0,2 quand la référence reste nette sur un geste rapide. Un
      obturateur à 0,5 en fait un fantôme translucide.
34. **Séquences d'images (rendus 3D) dans le film** : `MK.sequence()`. `window.__rm.settle()` attend le décodage de
    l'image avant chaque capture, sinon des images sautent au rendu.
35. **Musique de l'utilisateur** : quand la voix impose les coupes, on choisit le point de départ de la musique pour
    que les coupes tombent sur ses temps (`retime.py` → `music_start` ; MTN : 4 coupes sur 5 sur un premier temps).
36. **Logo et icônes de marque en vraie 3D** quand la référence montre un objet 3D : `blender/icon_build.py` (tuile
    épaisse biseautée, vernis, face imprimée reconstruite à partir du logo : emblème extrait par couleur, fond
    redessiné ; jamais le PNG plat qui tourne comme une carte).
37. **Une seule source de vérité pour le minutage** : la recette du film calcule l'objet et le déclare avec
    `MK.probe()`. `export_probe.py` relit ces valeurs image par image et en fait le job Blender. La 3D suit
    exactement le minutage validé au storyboard, sans logique recopiée.
38. Dans un job Blender, les chemins relatifs se lisent depuis le dossier du job. Écrire `out` en absolu, ou depuis le
    dossier du job.
39. Musique démarrée en plein morceau (`music_start` > 0) : fondu d'entrée de 0,25 s (`finalize.py`). Une attaque
    coupée net s'entend.
40. **Jamais d'angle ramené à [0, 360[ dans une animation 3D.** 356° puis 0° est interpolé à l'envers sur 356° pendant
    l'obturateur du flou de mouvement : traînée floue et faces fantômes. Un tour complet s'écrit 0 → 360. (MTN : carte
    « Solde » voilée et texte miroir pendant le retournement, disparus avec des angles continus.)
41. **Lumières de studio placées autour de l'objet, orientées vers lui, jamais près de la caméra.** Au téléobjectif,
    l'objet est loin. Une lumière près de l'objectif se retrouve dans l'axe miroir de l'écran et le voile de blanc.
    (Mesure MTN : en-tête #004B6E rendu (122,142,168) avec la lumière près de la caméra, (2,75,109) une fois corrigé.)
42. **Diagnostiquer un défaut 3D en l'isolant** avant de toucher aux réglages : rendu de contrôle face caméra et
    pipette (couleur rendue contre couleur de la texture), puis objet seul sous plusieurs angles. On corrige la cause
    mesurée, pas une supposition. (MTN : deux causes trouvées ainsi, les lumières et les angles.)
43. **Une surface très proche d'un écran ne s'y reflète pas** si la référence ne le montre pas : réflexion d'écran
    faible (`Specular IOR Level` 0,03, vernis 0,06). Sinon une carte retournée se dessine en miroir sous elle-même.
44. **Revue image par image du film contre la référence rejouée sur la même horloge, scène par scène, AVANT le
    rendu final** (planches référence | nouveau). Chaque écart vu est mesuré puis corrigé. Cas MTN, tous trouvés
    ainsi :
    - étoile pleine au lieu d'un trait creux ;
    - taille du premier mot différente de celle de la ligne ;
    - petites étoiles absentes aux croisements de la grille ;
    - carte qui rétrécit avec des coins arrondis au lieu de carrés ;
    - orbite à vitesse constante alors qu'elle accélère (`sine.in`) ;
    - pastilles qui doivent jaillir une à une ;
    - formes décoratives absentes autour de l'objet ;
    - 2 boucliers qui doivent coexister ;
    - instant d'effondrement de la tuile finale.
45. **Une lecture à l'œil se confirme par une mesure dès qu'une mesure est possible**, et la mesure gagne. (MTN :
    l'effondrement de la tuile lu à l'œil a d'abord été « corrigé » à tort par une courbe d'un autre élément, puis
    mesuré pour de bon : hauteur du cadre 230 → 194 → 62 px entre f592 et f598.)
46. **Mesurer un objet qui touche d'autres formes** (étoile prolongée par des lignes, texte entre des filets) : retirer
    d'abord les structures pleine largeur, ou ajouter un seuil de luminance propre à l'objet. Contrôler chaque valeur
    aberrante. (MTN : boîte de l'étoile faussée par ses propres branches à f10-f15.)
47. **Quand une recette change, réexporter les sondes (`export_probe.py`) AVANT de lancer le rendu Blender.** Sinon la
    3D suit l'ancien minutage.
48. **Commentaires en JavaScript** : jamais de `//` au milieu d'une ligne qui contient encore du code ; utiliser
    `/* */`. Une erreur de syntaxe bloque tout le film.
49. **Un enchaînement très rapide n'est pas forcément une coupe : le vérifier image par image.** (MTN : ce qui ressemblait
    à « pivot puis coupe vers le gros plan » est un tour complet continu de 360° en 7 images : face, tranche, dos,
    tranche, face, en fonçant vers la caméra.) Ce genre de geste se reconstruit par poses clés image par image, entre
    deux poses mesurées.
50. **Ne refaire que ce qui change.** Une pose identique à 360° près donne la même image. Pour corriger un passage,
    calculer les images vraiment différentes (angles comparés modulo 360°) et les rendre seules (`render_frames`),
    en gardant TOUTES les clés dans le job pour que le flou de mouvement reste continu.
51. **Jamais d'image cassée ni d'aperçu 2D dans le livrable.** Une image de séquence 3D manquante ou illisible est
    cachée ET arrête le rendu (`window.__mk_error`, vérifié après chaque `settle`). Le rendu final ne se lance
    qu'une fois TOUTES les séquences Blender complètes (compter les fichiers : nombre = images du job). L'aperçu
    `?r3d=0` sert seulement au minutage et à l'export des sondes ; il n'est jamais montré comme résultat sans le dire.
52. **Référence convertie (25 → 30 i/s) : ne jamais recopier ses images dupliquées.** Une image sur six répétée
    (pas identique au bit près après compression : mpdecimate la rate) crée des arrêts d'une image dans chaque
    mouvement. `mk.pulldown(vidéo)` la détecte (trous d'énergie réguliers, période et phase). Alors : rejouer et
    comparer sur les images DISTINCTES à la vraie cadence (style_compare le fait), retirer ces images des tables
    image par image (`dna_build` → `strip_pulldown`), rééchantillonner les poses suivies (`build_3d_job`). Une valeur
    « lue à l'œil » sur une image dupliquée est fausse : vérifier l'écart avec l'image précédente.
53. **Les sorties se mesurent jusqu'à la coupe et se calent sur la coupe.** Une scène finit souvent par un geste
    (groupe qui monte, téléphone qui glisse, mot qui rétrécit, grille qui explose) coupé en plein mouvement.
    Mesurer jusqu'à la DERNIÈRE image avant la coupe (un ajustement arrêté avant est tronqué et faux), puis le
    jouer en temps réel à la même distance de NOTRE coupe (`toCut`), jamais ralenti par l'étirement.
54. **Des gestes qui se chevauchent dans la référence gardent leur décalage mesuré.** Ne jamais attendre la fin
    de A pour lancer B si la référence lance B avant (ex. l'explosion de la grille démarre 0,5 s après le début
    du resserrement, pas à sa fin).
55. **Un suivi qui casse ne se fige pas.** Quand le flou casse le suivi de pose (z, angles qui sautent), arrêter la
    pose à la dernière image fiable et continuer avec le déplacement MESURÉ à l'écran (`screen_dx`, converti à la
    profondeur de l'objet), jamais un `clamp` seul : il gèle l'objet alors que la référence bouge.
56. **Couleur, inclinaison, fermeture : mesurer, pas lire.** Saturation de l'encre image par image (éclairs
    d'accent de 2-3 images), pente du bord bas d'un objet (sens et amplitude de la rotation), instant exact d'un
    geste rapide sur les images brutes. Une lecture à l'œil a donné ici −12° (mauvais sens) au lieu de +6,7°, et
    une fermeture 6 images trop tôt.
57. **Téléphone 3D : vérifier le contour et l'îlot au zoom pixel contre la référence.** Une vitre avant ou un îlot
    vernis miroir reflètent le studio blanc : bande blanche autour de l'écran, îlot qui vire au blanc. Vitre avant
    peu réfléchissante (spec ≈ 0,12, sans vernis), îlot noir mat avec sa lentille, cadre graphite non vernis.
    Recadrer le haut du téléphone (îlot + coin) réf. | nous au même instant, à la même échelle, avant tout rendu long.
58. **Deux horloges dans une recette : ne jamais les mélanger.** La timeline d'une scène tourne sur le temps de la
    RÉFÉRENCE (recalé) ; `frame(tn, tr)` reçoit `tn` (nouveau) et `tr` (référence). Comparer un instant mesuré sur
    la référence avec `tr`, un instant de la voix avec `tn` (`vo.words[i].start - new_start`).
59. **Un passage étiré pour la voix n'est pas une pause.** Si la référence y est pleine de gestes (mots qui
    arrivent, ligne qui se recentre), ces gestes se jouent en TEMPS RÉEL sur `tn`, ancrés sur les mots dits ;
    seule l'attente entre eux s'allonge. Sinon tout est ralenti (×1,29 ici) et la vidéo paraît « standard ».
60. **Un cadre qui épouse un texte épouse NOTRE texte** (demi-largeur de notre ligne + marge mesurée), pas les
    valeurs en pixels de la ligne de référence.
61. **Les objets 3D gardent l'angle de vue de la référence.** Si elle laisse l'objet en vue trois-quarts qui dérive,
    ne jamais revenir de face « par défaut » : de face = figé. La rotation propre d'un jeton se MESURE par le
    rapport des axes de sa silhouette (1 = de face, ~0 = de profil) image par image.
62. **Icônes qui tournent : de vrais modèles 3D** (`blender/tokens_build.py` : pièce, tuile, carte, décor sur les
    deux faces), rendus avec leurs poses (`export_probe.py --object tokens --kinds …`). Jamais une image 2D tournée
    en CSS : elle paraît bancale dès qu'elle quitte la face.
63. **Une méthode qui sert est enregistrée dans le skill tout de suite, sous trois formes.** (1) un script réutilisable
    dans `scripts/` (usage en tête, chemins en arguments, testé sur le cas réel) ; (2) la procédure pas à pas dans
    `references/verification.md` ou `workflow.md` ; (3) une règle numérotée ici avec le cas réel. Puis la copie
    installée et le zip sont mis à jour. Le skill est partagé : un autre Claude doit refaire le même travail en ne
    lisant que ses fichiers. Cas réel : les planches réf./nous, le zoom pixel, la mesure des mots, de la rotation par
    silhouette et de l'inclinaison par le bord bas étaient d'abord des scripts temporaires — devenus `frame_pairs.py`,
    `word_ink.py`, `silhouette_spin.py`, `edge_tilt.py`, `energy_bars.py`.
64. **Aucune image générée dans la vidéo finale quand l'objet peut être modélisé.** Chaque visuel fourni sous forme
    d'image (icônes, cadenas, objet produit) est un MODÈLE de design : on le reconstruit en 3D (Blender,
    `tokens_build.py` ou un nouveau constructeur), avec ses pièces mobiles séparées (anse du cadenas, couvercle,
    aiguille…) pilotées image par image depuis le film (`MK.probe(nom, {…, partie: valeur})`, `export_probe.py`
    garde les clés de pièces, `render_job.py` les anime). Vérifier avec une image fixe composée sur le film, contre
    l'image de l'utilisateur (proportions, couleur sous l'éclairage du film, pièce ouverte / fermée) avant le rendu.
    Le sens des rotations change entre CSS (y vers le bas, horaire > 0) et Blender (y vers le haut) : rz = −rotation.
    Seuls restent des images : logos de marque (posés sur un objet 3D comme texture) et captures d'écran d'app
    (texture de l'écran du téléphone). Cas réel : cadenas MTN (corps, anse chromée qui descend f440-f443, serrure).
65. **Un arrêt d'une image dans NOTRE film = souvent une table de mesures qui s'arrête trop tôt.** `energy_bars.py
    --holes` le trouve ; l'écart entre images consécutives le confirme (0,07 = image identique). Cause typique : la
    table image par image s'arrête avant l'événement suivant (carte mesurée jusqu'à f126, effondrement à f128 : la
    valeur est figée pendant f127). Mesurer la valeur manquante avec la MÊME méthode, en la validant d'abord sur les
    valeurs déjà connues (bord droit de la carte : 0,774 / 0,688 / 0,568 = la table), puis l'ajouter avec sa source.
66. **Jamais de pose figée avant le premier suivi fiable.** Si le suivi d'un objet 3D ne démarre qu'après le début du
    plan, prolonger le mouvement MESURÉ en arrière (`build_3d_job.py` segment `"extrap": {"src", "fit": [f0, f1]}`,
    ajustement linéaire sur une fenêtre propre, en écartant une première image hors tendance) au lieu d'un `hold`.
    Cas réel : téléphone figé 7 images au début de P3 alors que la référence tourne déjà (ry +0,4°/image).
67. **Zone morte = défaut, même si chaque geste est juste.** `energy_bars.py` sur toute la scène : là où la référence
    bouge en continu et nous presque pas, chercher ce qui, dans la référence, bouge ENTRE les événements : un cadre qui
    s'ouvre d'une seule courbe (pas par sauts à chaque mot), un mot qui continue de se poser après son apparition
    (−6,5 % mesuré). Avant de corriger un « trou », le confirmer par l'écart de pixels entre images consécutives : un
    trou de la courbe d'énergie peut être un artefact (lignes très fines), pas un vrai arrêt.
68. **Quand le suivi d'écran échoue (flou), mesurer l'angle par la SILHOUETTE.** Boîte sombre de l'objet image par
    image (rapport largeur / hauteur), convertie en angle avec les dimensions du modèle 3D et calée sur une pose
    suivie fiable (rapport mesuré / rapport du modèle). Cas réel : début de P3, suivi seulement dès f328 ; la
    silhouette donne −41° (f325) → −31,5° (f328, = le suivi : il était juste) → −26,5° (f330) : un quart de tour
    rapide qui freine net. Ne jamais écarter une pose suivie « hors tendance » sans la vérifier par une 2e mesure.
69. **Une scène possède des images ENTIÈRES.** Le moteur choisit la scène par numéro d'image
    (`new_start_frame <= k < new_end_frame`), comme `timing.json`, les séquences 3D (image 1 = `new_start_frame`) et
    `style_compare`. Avec un choix au temps, une coupe à 6,88 s laissait l'image 206 à la scène précédente : la
    première image 3D n'apparaissait jamais et la coupe arrivait une image en retard. Le test « attaque » ignore les
    2 images après une coupe (l'énergie de la coupe déborde par le lissage).
70. **Pas de vernis miroir sur une face qui porte un logo ou une image.** Un vernis net (coat 1, rugosité 0,04)
    reflète les fenêtres du studio HDRI en rectangles blancs qui coupent le logo dès qu'il est vu de trois-quarts.
    Face satinée (coat ≈ 0,35, rugosité du vernis ≈ 0,2, spéculaire ≈ 0,35) : reflets doux, logo lisible. À vérifier
    à l'image de contrôle sous l'angle le plus incliné de la séquence, pas seulement de face.
71. **Auditer les poses AVANT tout rendu 3D : `pose_audit.py job.json --first-frame N [--allow f0-f1]`.** Il signale
    les SAUTS (pic de rotation contre les images voisines, ex. un logo qui se redresse en une image à l'effondrement :
    40,9°), les objets FIGÉS (rotation < 15°/s, taille < 8 %/s, position < 5 %/s pendant > 0,3 s) et les objets
    PENCHÉS-IMMOBILES (face tournée > 20° sans tourner) : la plainte exacte de l'utilisateur sur le logo MoMo. Les
    immobilités qui sont celles de la référence (tuile fixe pendant l'orbite) se déclarent avec `--allow`, justifiées.
    Un rendu ne part pas tant que l'audit n'est pas « poses : OK ».
72. **Un objet qui porte un logo ou une image plate se présente presque de face et bouge toujours.** Un angle copié
    sur un objet de référence de forme différente (lettre 3D lisible de biais) ne s'applique pas tel quel à une tuile
    plate : posée à 5-10° (épaisseur visible), balancement continu (±10° / ±5°, 1 cycle/s, en temps réel `tn`),
    approche lente, redressement progressif avant une transformation (jamais en une image). Contrôle : une image fixe
    à deux instants du balancement, logo lisible et couleurs saturées.
73. **Un effet qui altère un texte (signes, glitch, brouillage) se mesure lettre par lettre et ne clignote jamais.**
    Référence A : 2 lettres sur 18 remplacées (11 %), des MOTS entiers retirés depuis la fin, une courte chaîne de
    signes seulement sur les 2 dernières images. Les remplacements sont décidés une fois (graine fixe, sur la ligne
    entière) puis les mots sont retirés : une lettre remplacée garde son signe et sa place. `MK.scramble` le fait.
    Un tel effet est montré à l'utilisateur sur une image du storyboard et validé avant le rendu : sinon il se lit
    comme un bug (cas réel : « En>oye:, », « %:v:##; » signalés par l'utilisateur).
74. **Audit de nervosité chiffré avant de livrer : `nervosity_audit.py timing.json reference_recalee.mp4 film.mp4`.**
    Par scène : passages étirés pour la voix (et leur facteur), énergie dans ces passages, vitesse des pics (p95),
    zones mortes de 0,3 s et plus, écart de chaque coupe au temps fort le plus proche. Chaque zone morte se comprend
    sur la référence (ce qu'elle fait à ce moment) et se comble par un mouvement MESURÉ de la référence (ex. P4 :
    nuage qui s'épanouit ×3,5 en 0,2 s puis dérive), jamais par une invention gratuite.
75. **« Notre plus » : s'inspirer de la DA, puis ajouter ce qui manque, validé sur maquette.** Quand le contenu de
    l'utilisateur laisse des zones vides (ex. moitié gauche vide autour du téléphone), proposer des ajouts : légendes
    reliées aux éléments, compteurs, chrono, code PIN, micro-étiquettes, appel à l'action. Règles : (1) seulement
    dans les zones vides de la composition ; (2) calés sur les mots dits et les temps de la musique ; (3) avec le
    vocabulaire de mouvement de la référence (ses eases et durées mesurées) et les couleurs de la marque ; (4) jamais
    de texte ou de donnée de marque inventée (code USSD, boutiques d'applications) sans confirmation. Planche
    `additions_board.py film.mp4 spec.json out.png` : image actuelle | maquette des ajouts | description du
    mouvement. Rien n'est construit avant la validation de l'utilisateur.
76. **Un storyboard d'ajouts se montre en RENDU RÉEL, jamais en croquis.** Des rectangles tracés et des textes posés
    à la main ont été jugés « banals » et « sortis du cadre » par l'utilisateur. Méthode : construire les ajouts dans
    le film derrière un interrupteur (`?plus=1`), rendre les images (`render_film.py --stills --query plus=1`), puis
    `additions_board.py … --base dir_actuel --plus dir_ajouts`, plus une planche de détails (états successifs, zooms).
    Règles de mise en page : un ajout reste DANS son conteneur (panneau, cadre) avec une marge (≈ 7 % de largeur),
    aligné en colonne, centré verticalement dans la zone vide, hiérarchie titre / sous-titre / état atténué.
    Un trait qui relie un texte à un objet 3D vise le point PROJETÉ à chaque image (`project_points.py` sur le job
    Blender → `window.P3PTS`), jamais une position fixe. Pastilles « verre dépoli » : fond blanc 82 % + flou 10 px,
    ombre douce, point de couleur, texte de marque centré avec de vraies marges, posées vers l'extérieur de l'orbite.
77. **Pièges de code trouvés en construisant les ajouts.** (1) Restaurer un texte en comparant `innerHTML` reconstruit
    l'élément à CHAQUE image dès qu'une animation y écrit un style : l'élément animé est détaché et le geste ne se
    voit plus (la montée de « payer, » était perdue) — utiliser un drapeau « a été modifié ». (2) Une échelle GSAP sur
    un élément SVG avec `transformOrigin` en px déplace l'élément (point parasite) : animer l'attribut (`r`, tracé
    par `stroke-dashoffset`) plutôt qu'une transformation. (3) Un trait jaune de 3 px posé sur une ligne de grille
    jaune disparaît : vérifier chaque ajout sur l'image réelle, pas dans le code.
78. **Storyboard général du film rendu, avant la livraison : `general_storyboard.py final.mp4 timing.json spec.json out.png`.**
    Toutes les scènes dans l'ordre, 4 à 6 images clés par scène avec leur instant, la phrase de la voix de la scène
    et une ligne qui décrit ce qui se passe. Il sert à la relecture globale de l'utilisateur (enchaînements, rythme,
    cohérence), en plus des planches de détails.
79. **Logos de tiers (boutiques d'applications, moyens de paiement, partenaires) : fichiers OFFICIELS seulement.**
    Ne jamais les redessiner. Les télécharger depuis la source officielle (Google : play.google.com/intl/…/badges ;
    Apple : developer.apple.com/assets/elements/badges/…) ou les demander à l'utilisateur ; même langue pour tous
    les badges ; même hauteur ; espace libre respecté ; apparition sobre (fondu + légère montée), jamais de rotation,
    de 3D ni de déformation. Retirer seulement la marge transparente d'un fichier pour aligner les hauteurs.
80. **Un geste de fermeture se mesure en largeur ET en hauteur.** Le cadre final de A se rétrécit d'abord en largeur
    (hauteur pleine, circ.in 0,267 s) puis se ferme en carré (expo.in 0,067 s) : une échelle uniforme ajustée tard
    ratait 0,2 s de geste et créait une zone morte (trouvée par `nervosity_audit.py`, confirmée par les écarts de pixels).
81. **Récupérer une référence partagée par lien : `fetch_reference.py <lien> ref.mp4`.** Pinterest (pin.it) sert un
    flux HLS à plusieurs variantes : `ffmpeg -i master.m3u8` prend la PREMIÈRE (256x144), inutilisable pour mesurer.
    L'outil lit chaque RESOLUTION, prend la plus grande (736x414 au maximum sur Pinterest pour du 16:9) et ajoute la
    piste son séparée. Toujours noter la résolution réelle de la référence dans le rapport.
82. **Un design fourni en PSD se DÉCOMPOSE, il ne se recadre pas : `psd_decompose.py design.psd analysis/psd/`.**
    Sortie : `composite.png` (la cible à égaler), chaque calque en PNG détouré à sa position, et `layers.json`
    (ordre, groupe, opacité, mode de fusion, boîte en px et normalisée, et pour les TEXTES : contenu, police,
    taille, couleur, approche). Les textes sont recomposés VIVANTS dans le film (taille = px PSD / hauteur du
    canevas × H) ; seules les images que le code ne refait pas (photo, rendu 3D, reflets) restent des calques PNG.
    Les effets de calque (ombre, lueur, contour, dégradé) ne sont pas cuits par psd-tools : les refaire en code
    depuis leurs valeurs ou demander le PNG aplati de ce calque. Vérifier en superposant le rendu du film à
    `composite.png` (écart de pixels) avant d'animer. Testé : calques pixel ; calques texte à vérifier sur le
    premier vrai PSD (noter le résultat ici). Résultat (affiche Master Skills, 3543x4724, 36 calques) : 17 textes lus avec
    police / taille / couleur ; les valeurs « String » de psd-tools s'écrivent en JSON par leur `.value` (corrigé) ; les
    PSD de plus de 30 Mo passent par un lien Google Drive public téléchargé avec `gdown <ID>` (gros fichier : OK).
83. **Un mot du script absent de l'alignement n'est pas forcément absent de la voix.** Le recogniseur peut fusionner
    des mots courts (« dix mille » non écrit entre « unique » à 28,5 s et « francs » à 29,5 s). Vérifier : énergie de
    la voix par tranches de 0,1 s, puis transcrire SEULEMENT ce segment (audio passé en tableau numpy à faster-whisper
    si la lecture de fichier échoue sur la version d'`av`). Cas réel : « 10 000 » entendu à 29,22-29,54 s.
84. **Le design PSD se RECOMPOSE en code puis se PROUVE contre `composite.png` avant toute animation.**
    `psd_rebuild.py analysis/psd build/poster.html --fonts assets/fonts --skip <logos interdits, copie aplatie>
    [--text i="texte corrigé"] [--nudge i=dx,dy,dtrack]` puis `psd_compare.py build/poster.html analysis/psd
    build/poster_compare.png --json …`. Règles de géométrie du texte (mesurées sur un cas réel, écart ≤ 1 px) :
    taille = `size × échelle de transform` ; origine (tx, ty) de transform = LIGNE DE BASE de la 1re ligne ;
    justification 0 gauche / 1 droite / 2 centre autour de tx ; tracking/1000 em ; interligne = leading × échelle ;
    ligne de base CSS = (line-height − (asc + desc) × taille)/2 + asc × taille (métriques hhea du fichier de police).
    Effets : `psd_decompose` écrit leurs valeurs complètes (`effects_values`) : incrustation couleur = masque CSS du
    PNG peint de la couleur ; incrustation dégradé = posée sur la boîte d'ENCRE du calque, centre + décalage, longueur
    = étendue × échelle, arrêts CSS TRIÉS dans l'ordre de la ligne CSS (sinon Chrome les écrase en aplat blanc).
    `background-clip:text` sur un bloc dont l'interligne est < taille coupe les lettres : peindre un `span`
    inline-block rembourré (padding ±taille, marges négatives). Une police d'une autre version que celle du graphiste
    peut décaler un gros titre de quelques px : corriger avec `--nudge` à partir des écarts gauche/droite du rapport.
    Ne pas ajouter de grain aléatoire pour « coller » (il augmente l'erreur) : le grain vient du calque de texture.
    Cas réel (affiche Master Skills, 3543×4724 → 886×1181) : erreur moyenne 5,7/255, 14 textes sur 15 à ≤ 2 px
    (le 15e diffère par la correction voulue « Tought » → « Thought »). Chaque élément porte id="L<index>" : le film
    anime CES éléments, il ne les remet jamais en page à la main.
85. **Film à plusieurs références (fusion) : UNE horloge, le temps de la voix + un décalage.** `W(v) = v + VO` donne
    l'instant film de chaque mot (alignement `audio_prep --align`) ; chaque scène emprunte à UNE référence et cite
    son fichier de mesures (`analysis/R*/fits*.json`) dans le commentaire du code. Le décalage VO se choisit pour
    que la première entrée de texte MESURÉE de la référence d'ouverture tombe sur le premier mot (cas réel : R3 fait
    entrer son mot à 1,9 s → VO = 1,9 s). Le début de l'extrait musical se CALCULE : `music_start = drop − W(mot clé)`
    (cas réel : drop 32,113 s sur « Master » = film 13,04 s → extrait à 19,07 s ; la cassure du morceau tombe
    alors sur le dernier mot). Mixage : `finalize.py … --voice-offset VO --music-offset 0 --music-start <calculé>`.
    Une vidéo montrée DANS le film (référence, démo, exemple) passe en séquence d'images JPG (`ffmpeg -r 30`), jamais
    en <video> : la page change le `src` à chaque image et `__rm.settle()` attend `img.decode()` (rendu exact).
86. **La PREUVE qu'un skill marche = la même séquence, référence | recréation, côte à côte et synchronisées.**
    Recréer un passage court (4-5 s) de la référence pour une MARQUE FICTIVE (nom, couleurs, textes, chiffres
    inventés ; jamais une vraie marque sans accord) en reprenant ses mesures (fits) — page autonome
    `demo/<marque>.html` rendue avec `render_film.py` —, puis montrer les deux séquences dans deux panneaux du même
    écran, lancées à la même image et étiquetées « RÉFÉRENCE » / « RECRÉÉE · MARQUE FICTIVE ». Cas réel : R2
    (zelios) → « Zuvo » (orange #FF6B1A / pétrole #0E3B43, FCFA), mots, glissé, écran en perspective, clic.
87. **Anti-« PowerPoint » : un film motion n'est jamais une suite d'éléments qui apparaissent puis attendent.**
    Retour réel d'un utilisateur sur un brouillon (Master Skills v1) : « ça ressemble à de l'animation PowerPoint ».
    Causes trouvées : textes en simple fondu + montée de 12 px puis immobiles ; plans tenus sans mouvement ; coupes
    en flou au lieu de transitions motivées ; aucun flou de mouvement ; caméra figée ; un clic de curseur qui ne
    touche pas le bouton. Contrôles OBLIGATOIRES avant de montrer un storyboard :
    (a) aucune image n'est immobile plus de 0,3 s : caméra en dérive continue + parallaxe (3 plans de profondeur) ;
    (b) le texte s'anime par LETTRE ou par syllabe (masques, rotation 3D, décalage, échelle, couleur), avec
        dépassement et flou de mouvement, et RESSORT animé (jamais un simple fondu) ;
    (c) chaque transition est un raccord : un élément de la scène A DEVIENT un élément de la scène B (forme, couleur,
        position) — fil conducteur unique (ex. le triangle de l'affiche) ; le flou seul n'est pas une transition ;
    (d) flou de mouvement sur tout ce qui bouge vite (`__rm.blurAt` : 8-16 échantillons, obturateur 180°) ;
    (e) mouvement secondaire : lueurs, particules, reflets, respiration des éléments tenus ;
    (f) un curseur qui clique : le point chaud de la main est sur la cible à l'image du clic (mesurer le rectangle
        de la cible dans la page et vérifier), la cible réagit (enfoncement, onde, changement d'état) ;
    (g) comparer image par image avec la référence la densité de mouvement (`energy_bars`, `nervosity_audit`) :
        l'énergie moyenne du film doit être au moins celle de la référence.
    (h) une preuve fournie par l'utilisateur (vidéo originale + recréation) s'insère dans son format natif
        (9:16 → deux téléphones 3D côte à côte), jamais recadrée ni remplacée par une démo inventée.
88. **Vrai motion : outils et méthode (Master Skills v2).** `engine/mk-kinetic.js` (lettres, sorties animées,
    dérive de caméra + coups sur les temps forts `build/beats.js` = beats de `audio_plan` force > 0,3 ramenés en temps
    film, curseur posé sur la cible LUE dans la page, clic + réaction du bouton). Flou de mouvement du film :
    `window.__rm.blurAt = t => [6, 0.5]`. Fil conducteur : un seul objet (ici le ▶ de l'affiche) traverse les
    scènes et se transforme (trait → ▶ → traînée d'où sortent les lettres → éclats → prismes ; reflet de visière →
    trait → champ de saisie ; pellicule → deux images → deux téléphones). Téléphones 3D (preuve en 9:16) : le MÊME
    `phone_build` Blender que MTN, un job par téléphone, écrans = séquences PNG remises au rapport de l'écran
    (0,4717 : bandes noires en haut/bas, jamais étirées), poses calculées image par image (arrivée expo.out 1,17 s
    mesurée R2, décalage 3 images, flottement continu, plongée power3.in qui sert de raccord). Débit Cycles mesuré
    sur 4 cœurs : ~30 s/image à 10-16 échantillons + débruitage, `-t 2` par job en parallèle ; NE PAS lancer un rendu
    Chromium en même temps (débit divisé par 3) ; reprendre un rendu interrompu avec `render_frames: [f0, f1]`.
    Un reflet blanc passager sur l'écran pendant une rotation est réaliste ; un écran laver une fois posé ne l'est pas
    (vérifier une image posée).
89. **La référence donne le MOUVEMENT, l'affiche de l'utilisateur donne le BRANDING — jamais l'inverse.**
    Cas réel (Master Skills v3, réf. lute) : le film copiait les aplats menthe de la référence en cyan → l'utilisateur :
    « il faut utiliser les couleurs, typo, etc. de l'affiche ». Traduction rôle par rôle : aplat d'accent de la réf. →
    le dégradé du bandeau de l'affiche (#2E8BFF→#0A4FD0, texte blanc) ; pilules → même dégradé, coins de l'affiche
    (6 px) ; mot d'accent → la couleur du ▶ (#00D2FF) ; grands mots → la graisse et le dégradé blanc→gris du titre de
    l'affiche ; petites lignes → les capitales très espacées de l'affiche (0,55 em) ; trois éléments → les trois
    pastilles numérotées de l'affiche (cyan / rouge / bleu) ; prix → l'onglet + la police Clash de l'affiche ; logo →
    ▶ + « Master » léger au-dessus de « Skills » comme sur l'affiche. FOND : jamais un dégradé inventé — une plaque
    16:9 composée des calques d'ambiance du PSD (fond, lueurs à incrustation couleur, texture lumière douce, prismes
    en mode écran), sans le sujet, rendue par une page Chromium (`build/plate.html`) puis animée en dérive lente.
    Les aplats ne prennent pas de vignettage (un aplat de la réf. est plat).
90. **(Mode Studio ; en mode Rapide, le « décalque » se limite aux pistes mesurées des éléments clés, et la règle « on ne devine jamais » reste entière.) PRINCIPE FONDATEUR (exigé par l'utilisateur après 3 versions refusées) : on DÉCALQUE d'abord, on adapte
    ensuite. Claude ne devine plus jamais.**
    Étape 1 — DÉCALQUE (méthode reverse-motion) : la référence est reconstruite en code scène par scène, mesurée
    avec TOUS les outils (`track_elements`, `track_textbox`, `track_quad`, `track_template`, `fit_easing`,
    `register.py` en mode encre, plaques `extract_plate.py`, `ghost_guard.py`), et comparée image par image à
    l'original (`compare.py` / `assemble.py` : SSIM ≥ 0,98 par image visé, Delta E, `ghost_runs`, `missing_runs`,
    `colour_runs`, anomalies = 0). Tant que le décalque n'atteint pas ce niveau, AUCUNE adaptation.
    Étape 2 — ADAPTATION : on garde le fichier de scène décalqué (mêmes timelines, mêmes caméras, mêmes eases
    mesurés, mêmes instants) et on ne remplace QUE le contenu : textes (`BRAND.texts`, corps du mot original),
    couleurs (`BRAND.colors`, y compris les plaques), visuels (images/3D de l'utilisateur à la place des
    visuels de la réf., posés sur les mêmes pistes / quadrilatères mesurés), fond (plaque du branding).
    Contrôle : `rhythm.py` doit dire « identique » (décalage 0). Le calage voix se fait en choisissant le
    décalage global de la voix, jamais en re-minutant les animations de la référence.
    Interdits : réinterpréter un bloc « dans l'esprit » de la référence ; inventer un ease, une durée, une
    position ; remplacer une mesure par une impression.
91. **Décalque par boîtes mesurées (méthode éprouvée sur la réf. lute, scène 1 : SSIM 0,982 au 1er passage).**
    (1) police : `font_search.py` sur 4 mots nets (catalogue `get_fonts.sh` ; les polices qui font planter FreeType
    sont sautées) ; (2) fond : séquence de plaques par image, éléments masqués + `cv2.inpaint` en 1/4 de résolution
    (le fond d'une réf. bouge : 7 niveaux d'écart en 1,7 s sur lute) ; (3) `box_tracker.py` : chaque élément (lettre,
    pièce de logo, point, pilule) suivi en boîte depuis une image clé propre, identités stables, fusions découpées ;
    corriger à la main les images ambiguës APRÈS les avoir regardées (ex. le haut d'un « u » = deux fûts séparés) ;
    (4) `engine/mk-boxreplay.js` : chaque lettre posée sur sa boîte (échelle commune du mot = largeur d'une lettre
    toujours entière, lissée ; haut = haut mesuré ; ligne de masque = bas commun des lettres qui montent ; ligne de
    base RÉELLE mesurée dans la page, jamais l'ascent de police) ; sprites de logo étirés dans leur boîte, alpha
    par projection fond→couleur ; (5) graisse balayée et mesurée (« lute » 560, « is » 380 : deux graisses dans un
    même mot) ; (6) flou de mouvement seulement là où l'original est flou (`blurAt`). Puis `compare.py` image par
    image ; regarder les pires images ; corriger ; re-mesurer.
92. **Master King travaille sans limite : jusqu'à 2 sous-agents en parallèle, chacun armé de TOUTE la méthode.**
    Quand un décalque ou un film est long, l'agent principal découpe le travail en lots INDÉPENDANTS (plages
    d'images / scènes) et confie au plus 2 lots à des sous-agents (outil Agent, en arrière-plan), puis fait le
    sien. Chaque brief de sous-agent est autonome (il démarre sans contexte) et contient obligatoirement :
    les chemins (référence, dossier projet, skill), les règles à lire (rules.md 90-92, METHODS.md de
    reverse-motion), les outils et leur ordre (cartographie → police → `box_tracker.py` → `mk-boxreplay.js` →
    `compare.py` → corrections → re-mesure), la plage d'images EXACTE à couvrir, les conventions communes
    (736×414 natif, 25 i/s, fond `assets/bg/NNNN.jpg`, police Inter, `window.__rm` avec `seek` qui ne renvoie
    rien), les fichiers qu'il possède (ses `scenes/sN.html`, `tracks/sN*.json`, `out/sN*`) et ceux qu'il ne doit
    PAS toucher, l'objectif chiffré (SSIM moyen ≥ 0,98 par scène, pires images regardées, 0 texte en double), et
    le format du rapport (scores par scène, pires images, défauts restants, chemins des fichiers). L'agent
    principal relit chaque rapport, regarde lui-même les pires images, et ne valide qu'avec les mesures.
    Limites matérielles : 4 cœurs → un seul rendu lourd (Blender / film complet) à la fois ; les rendus de
    scène courts peuvent tourner en parallèle.
93. **TOUT est recréé en code, rien n'est extrait de la référence (exigence de l'utilisateur).** Écrans d'interface
    (tableau de bord, graphiques, listes), logos et icônes (redessinés en SVG vectoriel d'après les formes
    mesurées), objets 3D (sphères, pièces, téléphones : Blender ou WebGL/CSS), avatars, éclats, lueurs : tout est
    une reconstruction paramétrable posée sur sa piste mesurée. Seul le fond ambiant peut rester une plaque par
    image. Raison : à l'adaptation, chaque élément est REMPLACÉ par le contenu de l'utilisateur sur la même piste
    (même image, même quadrilatère, même boîte) ; un élément extrait ne se remplace pas et provoque des décalages.
    (Ceci remplace, pour Master King Motion, la tolérance de reverse-motion sur les « visuels non recréables ».)
    Images / vidéos de personnes ou d'objets réels (photo, tournage) : Claude ne les invente pas en code ; il
    fournit les PROMPTS INTÉGRAUX de génération (sujet, cadrage, objectif, lumière, palette de la marque, fond,
    format, durée et mouvement pour une vidéo, éléments à éviter), un par plan, calés sur la durée et la piste
    mesurées du plan de la référence, puis intègre les fichiers reçus sur cette piste.
94. **Ordre de travail après le décalque (obligatoire, chaque étape validée avant la suivante) :**
    (1) Contrôle final du décalque : scores par scène, pires images regardées, rapport à l'utilisateur.
    (2) SCRIPT DE VOIX adapté : Claude écrit le texte de la voix off de l'utilisateur EN FONCTION DU RYTHME et du
        contenu de la référence : un bloc de texte par bloc mesuré, longueur calculée sur la durée du bloc
        (~2,5 à 3 mots/s en français, mots clés posés sur les instants forts mesurés : mot qui apparaît, coup de
        musique, drop), et il le FOURNIT à l'utilisateur (tableau temps réf. | durée | texte | mot clé sur l'instant)
        pour qu'il génère la voix ; on ne déforme jamais le rythme de la référence pour coller à une voix existante.
    (3) Prompts intégraux des images / vidéos réelles nécessaires (règle 93).
    (4) STORYBOARD de l'adaptation en rendu réel (images du décalque avec le contenu de l'utilisateur à la place),
        validé par l'utilisateur.
    (5) Seulement alors : rendu final, mixage, contrôle `rhythm.py` (identique à la référence).
95. **Boîte à outils du décalque complet (réf. lute, 950 images) et plafonds mesurés.**
    Textes : `scripts/wordfit/track.py` (gabarit Inter ajusté par image : corps, plume, flou directionnel, opacité) →
    0,96-0,99. Sorties floues de mots : centroïde + masse d'encre par mot (insensibles au flou) → 0,98. Écrans / plans
    d'interface / surfaces rigides : `homography_track.py` (ORB + RANSAC, recalé sur l'image clé) donne la perspective
    EXACTE image par image ; le contenu est recréé par `vectorize_image.py` (SVG par calques de couleurs, flou 0,5-0,6 px)
    et posé en `matrix3d` sur les coins (plafond mesuré ~0,88-0,90 sur une interface très détaillée : le mouvement est
    exact, le détail fin est remplacé à l'adaptation de toute façon). Traits animés / pointillés / comètes / croix :
    `vectorize_masked.py` ou `wordfit/vtrace.py` (vectoriel + lueur mesurée). Groupes rigides (étiquette + lueur + texte) :
    base mesurée + affinité par image. Pièges vus : une plaque de fond limitée à une plage (s6_bg jusqu'à 606) → image
    cassée au-delà ; une boîte mesurée seulement jusqu'à une image → élément disparu après (prolonger la dernière valeur) ;
    une mesure ajoutée à un mot déjà couvert par une boîte → texte en double ; lire la vidéo hors plage extraite.
96. **Surfaces suivies (écrans, téléphones, étiquettes, pièces) : chaîne « médiane redressée → ECC → calques ».**
    Mesuré sur S10 lute : 0,849 → 0,912 (bureau 0,55 → 0,85 pendant le mouvement, pièces 0,87 → 0,94).
    (a) `rectify_median.py ref.mp4 piste.json planche.png --frames a-b --occ occ.json [--drop-light 150]` : chaque image
        est redressée sur le canevas, la MÉDIANE par pixel (hors occultations : étiquette posée dessus, curseur ; hors
        texte avec --drop-light) donne une planche de mesure propre, sans bruit ni flou passager. Ne JAMAIS vectoriser
        une seule image : une étiquette posée sur l'écran y est cuite, le contraste est faux.
    (b) `homography_refine.py ref.mp4 piste.json planche.png out.json --key K --occ occ.json` : chaque image est
        recalée par ECC (MOTION_HOMOGRAPHY, masque = partie visible) sur la MÊME planche, en partant de l'image clé
        vers les deux bouts (départ = voisine recalée). Corrélation 0,94-0,999 là où ORB sautait de 40 px. Les images
        en fouet (cc < 0,55 ou saut) gardent la piste ORB. Puis on REFAIT (a) avec les coins recalés (planche plus nette).
    (c) `vectorize_image.py --image planche.png out.svg --layered --thr 4 --kd 48 --sigma 4 --up 4 --eps 0.2 --smooth 0
        --mina 0.2` : FOND lisse (posterisé puis flouté par filtre SVG) + DÉTAILS (pixels qui s'écartent du fond)
        quantifiés à part → les petits textes clairs et bougies gardent leur couleur (mode simple : contraste écrasé,
        0,855 ; calques : 0,885 sur un plafond planche de 0,919).
    (d) Pièges : `filter: blur()` sur une <img> en matrix3d n'est pas en cause, mais VÉRIFIER en isolant le calque
        (comparer capture du calque seul ↔ warp Python de la planche) avant d'accuser le navigateur.
97. **Faces et textes des étiquettes / boutons.** Face = médiane redressée avec `--drop-light` (texte exclu), trou du
    texte comblé (inpaint + flou), vectorisée en calques (reflet diagonal, biseau, bord) ; le TEXTE reste en vraie police
    par-dessus, recalé sur la boîte d'encre blanche mesurée DANS le canevas (corps, interlettrage, centre y).
    Étiquette partiellement cachée derrière une autre (« Mobile » sous « Desktop ») : mesurer le bord bas visible par
    colonnes (régression gauche/droite = inclinaison), poser la face sur la piste de l'étiquette de devant décalée de
    ces profondeurs, luminosité mesurée (~0,9).
98. **Phrases : vraie mise en page de ligne, jamais un mot par boîte.** Une ligne = un élément texte (espaces exacts du
    navigateur) ; corps / graisse / opsz / position ajustés PAR SYNTHÈSE (rendus candidats comparés par corrélation sur
    la bande de la ligne de référence ; ex. Inter 400, 22,53 px, opsz 14 → 0,866) ; chaque mot reste un span
    inline-block animé avec ses mesures (opacité, dy). Placer chaque mot sur sa boîte d'encre fausse les espaces
    (« ecosystem- ») et la hauteur (jambages).
99. **Sorties en profondeur.** Mesurer l'échelle de chaque couche (corrélation à échelles multiples autour d'un
    centre) et la trajectoire des objets du premier plan (centroïde + étendue de la tache colorée) image par image.
    Un flou qui croît du centre vers les bords est une DÉFOCALISATION (flou gaussien par mot ∝ distance au centre,
    flou croissant sur les objets), pas un flou de mouvement : les traînées de sous-images y font perdre des points.
100. **Objets qui passent DEVANT une surface immobile (curseur, main, pastille) : rotoscopie vectorielle par
     différence.** Planche médiane de l'état (objet masqué par un disque autour de sa position) ; à chaque image,
     |image − planche| > 45 et saturation > 60 dans un disque autour de la position attendue → plus grande composante
     → contour simplifié (SVG par image) + dégradé haut/bas mesuré (couleur qui glisse rose → jaune → turquoise).
     S6 lute : curseur 3D exact (forme, taille, orientation, couleur) au lieu d'une flèche dessinée ; scène 0,827 → 0,876
     avec les planches par état (bouton, carte, icônes, avatars vectorisés ; textes retirés par écart au fond médian
     puis rejoués en vraie police).
101. **Coupes et fenêtres de flou : mesurées, jamais posées à l'œil.** Variance du laplacien de la référence image par
     image (net ~400-700, flou < 150) → fenêtres `blurAt` et force (obturateur 0,5 pour un flou modéré). Vérifier le
     CONTENU autour d'une coupe supposée (S8 : le plan C durait jusqu'à 538, la piste D 532-538 suivait en fait C).
     Panoramique sur une interface : `track_pad.py --auto 736,414 --frames a-b` agrandit le canevas à la boîte exacte
     vue par toutes les images, sinon bords vides.
102. **Planche ou formule : mesurer les deux.** Une forme plate et unie (pastille FRIENDS : rectangle menthe + texte)
     déjà reconstruite analytiquement (affinité + flou mesurés) bat la planche vectorisée (0,92 contre 0,90 : bord de
     planche, rognage). La chaîne des règles 96-97 est faite pour les surfaces RICHES (interfaces, pièces, boutons
     texturés) ; garder la meilleure des deux par scène, chiffres à l'appui.
103. **Aucune image cassée.** `render.mjs` s'arrête si une <img> visible a un fichier introuvable (largeur naturelle 0).
     Vu sur S2 lute : le logo « lute » pointait vers un PNG absent ; 20 images rendues avec l'icône d'image cassée sans
     erreur. Logo recréé en SVG (médiane des images fixes → alpha d'encre entre fond menthe et couleur d'encre mesurée →
     contour sur-échantillonné) : S2 0,976 → 0,989. Mêmes logos S1/S12 (markA/markB) : 0,972 → 0,982 et 0,960 → 0,973.
104. **Assemblage sans 2e génération.** Scènes opaques bout à bout : `compose.py` CONCATÈNE les fichiers (ffmpeg
     concat, `-c:v copy`) au lieu de décoder / ré-encoder. Le ré-encodage (2e sous-échantillonnage de la chroma) coûtait
     ~0,01 SSIM par scène (S1 0,982 → 0,971 ; global lute 0,925 → 0,934 rien qu'en le supprimant). Toujours comparer le
     score d'une scène dans `report.json` à son score isolé : un écart = problème d'assemblage, pas de scène.
105. **Audit de structure de l'adaptation (avant le rendu final, obligatoire).** Rendre l'adaptation complète puis
     `adaptation_audit.py decalque.mp4 adaptation.mp4 out --accent R,G,B` : par image, OUBLI (structure du décalque sans
     rien dans l'adaptation à 9 px), FANTÔME (l'inverse à 25 px), RESTE (pixels encore dans la teinte d'accent de la
     référence), SCÈNE VIDE. Puis planche contact décalque | adaptation (1 image / 16) regardée en entier.
     Vu sur Master Skills : (1) S9 « Access [logo] lute anywhere » adapté sans le logo ni le nom de marque = structure
     de la DA cassée (oubli 0,6 → 0,03 en remettant « Accès ▶ Master Skills [à vie.] ») ; (2) interfaces génériques
     posées seulement sur la zone vue à l'image clé d'un canevas agrandi → zones vides pendant le mouvement de caméra :
     une interface sur canevas suivi doit REMPLIR tout le canevas (mise en page en W x H). Les signalements attendus
     (formes du logo différentes, textes plus longs, éléments ajoutés à la demande) se justifient un par un.
     Piège de script : `while read … ; node …` — node lit l'entrée de la boucle et saute des lignes : `node … < /dev/null`.
106. **Typo de l'adaptation = typo de la marque, rôle par rôle.** Demander / appliquer la police par rôle (ex. Master
     Skills : Poppins partout, Clash Display UNIQUEMENT pour le prix). Changer de police = relancer l'adaptation des pistes
     (largeurs différentes → corps et positions recalculés), jamais un simple remplacement de nom.
107. **Nouvelle musique sur un décalque.** Ne jamais déformer le rythme des images. (1) Tempo : ramener la musique
     au rapport simple le plus proche du tempo de la référence par un étirement ≤ 3 % (ex. 95,7 → 93,3 BPM = 2 temps
     de musique pour 3 temps de la réf. 140 BPM, atempo 0,975). (2) Point de départ : balayer le morceau au centième de
     seconde et maximiser la force d'attaque (onset) sur les coupes majeures (poids 2) et les entrées mesurées
     (poids 1) ; départager par la corrélation de la courbe d'énergie avec celle de la référence. (3) Mix : voix calée
     bloc par bloc (transcription mot à mot faster-whisper → atrim/adelay, étirement ≤ 1,1), musique compressée par la
     voix (sidechaincompress), loudnorm −14 LUFS, fondu de sortie sur le logo.
108. **Contrôle final du rythme : deux comparaisons.** `rhythm.py ref final` ET `rhythm.py decalque final`. La
     seconde doit dire « identique » (l'adaptation n'a rien décalé) ; la première ne peut pas dépasser le score du
     décalque lui-même contre la référence (lute : décalque 29/35, adaptation 28/35 à ±1 image).
109. **Livraison en HD.** Le décalque se mesure à la résolution de la référence (736 × 414), mais tout étant en code,
     le film se rend en 1920 × 1080 par `render.mjs … --w 736 --h 414 --scale 2.608696` (densité de pixels), sans
     changer une seule piste. Ne jamais livrer à la résolution de mesure.
110. **Pas de tremblement : lisser les pistes et rendre au sous-pixel (retour utilisatrice : « tout tremble, mécanique »).**
     Mesuré sur l'adaptation Master Skills : corps des mots qui « respire » de 1 à 4 % d'une image à l'autre,
     positions qui vibrent (2e différence 1-16 px), texte qui avance par sauts d'un pixel (irrégularité 0,36 contre
     0,024 dans la référence). Un décalque copie le bruit de mesure ; une adaptation à livrer doit l'enlever :
     `smooth_tracks.py tracks/ --backup tracks_raw/` (Savitzky-Golay 7 images ordre 3 sur toute table {image: valeur},
     sauts réels > 6 unités protégés : départs, arrivées et instants inchangés) + `will-change:transform` sur les
     textes (calque composité = position au sous-pixel). Contrôle : centroïde sous-pixel des glissements lents,
     irrégularité comparée à la référence (S12 : 0,36 → 0,15). Rendu final en HD (règle 109) : pas de pixel visible.
111. **Voix : couper sur les SILENCES, caler chaque segment sur SON mot.** (1) Jamais couper sur la fin de mot donnée
     par la transcription (elle arrive trop tôt : « formation » amputé) : segments = parole réelle entre silences
     détectés (silencedetect −34 dB, 0,12 s). (2) Un segment par idée, calé sur l'apparition de son mot clé, pas une
     phrase entière sur un seul instant (dérive de ±1,5 s sinon). (3) Si l'ordre des images l'exige, réordonner les
     segments (fin : « le 10 novembre » sur la date, puis « Master Skills » sur le logo). (4) Vérifier en
     RETRANSCRIVANT la voix calée : écart mot clé ↔ image ≤ 0,3 s, ou mot dit pendant que l'élément est à l'écran.
112. **Captures réelles fournies par l'utilisateur = interface recréée en code** (pas collée en image) : maquette à la
     taille de la capture (ex. 2000 px de large) réduite par transform au canevas suivi, contenu adapté au film
     (texte du script, voix sélectionnée, prise du projet).
113. **Fond STABLE dans l'adaptation (cause n°1 du « tout tremble »).** Les plaques de fond inpaintées image par image
     gardent le bruit de compression de la référence ; recolorées et réencodées, elles font « grouiller » tout l'écran
     (coin vide : 0,06-0,09 de vibration contre 0,002 dans la référence ; fond fixe = 0,000). Mesure : énergie des
     changements qui s'INVERSENT d'une image à l'autre (−Δ1·Δ2 > 0) dans une zone vide. Correction : une plaque
     moyenne par scène (ou fondu lent entre plaques clés si la référence a un fond qui bouge vraiment), jamais une
     plaque par image dans une adaptation. Le décalque peut garder ses plaques image par image (fidélité SSIM).
114. **Script de voix = UNE LIGNE PAR PLAN, durée max mesurée (leçon Master Skills).** Un script écrit « par idée »
     (11 phrases) tombait faux : la phrase Tought durait 2,8 s pour un bouton de 1,5 s, « Reverse Motion décortique une
     vidéo, image par image » 3,3 s pour un plan de 2,2 s. Corriger après coup par des PAUSES dans l'image (ralenti
     jusqu'à 10 % puis reprise) est refusé à l'œil : sur un montage nerveux, la pause casse l'élan et « saute ».
     Méthode : lister les plans mesurés (fenêtre d'affichage de chaque élément clé), écrire une ligne par plan avec
     durée max = fenêtre et nombre de mots = 2,5-3 mots/s × durée, marquer le mot clé à poser sur l'apparition ; prise
     unique avec [pause 0.8s] entre lignes (découpage sur les pauses), puis calage ligne par ligne (≤ 1,08× si une
     ligne déborde) et vérification par retranscription (écart ≤ 0,2 s). Le film garde la durée et le rythme de la
     référence.
115. **Stabiliser l'adaptation là où la mesure « respire » (retour : textes qui tremblent, curseur mécanique, caméra
     bancale).** (1) Un GROUPE porté par une boîte mesurée (bouton + carte) : la hauteur mesurée variait (69-106 px, bas
     qui s'estompe) → le groupe sautait de ±4 px pendant l'arrêt (5,9 px/image). Remplacer par des courbes ajustées sur
     la mesure : entrée (décélération cubique), ARRÊT IMMOBILE, sortie (accélération) → 0,5 px/image, plus stable que
     la référence. (2) Un texte dans ce groupe : pose fixe, jamais sa propre piste en plus (double mouvement).
     (3) Un objet rotoscopé image par image (curseur) : une seule forme vectorielle propre sur la trajectoire et la
     taille lissées, couleur conservée. (4) Un logo qui se pose : lisser la construction puis le FIGER jusqu'à la
     sortie (vérifier les copies des données dans d'autres scènes : S12 avait sa propre copie de S1A).
     (5) Caméra sur interfaces : si l'utilisateur la trouve bancale, remplacer l'homographie mesurée par une caméra
     propre à plat (cadrage départ → arrivée, ease sinusoïdal, zoom ×1,1-1,35 vers la zone utile, fouets aux instants
     de coupe de la référence avec flou de mouvement) et la faire valider en storyboard (début / milieu / fin par plan
     + extrait animé).
116. **Téléphone réaliste dans une adaptation = vrai smartphone 3D Blender composité sur la piste redressée.** Rendre
     `phone_build.py` (job `render_job.py`, fond transparent, Cycles 20 éch., pose fixe légèrement tournée ry −14°,
     écran = séquence de la vidéo de l'utilisateur) UNE image par image du film où il est visible, puis poser la
     séquence PNG sur le rectangle redressé de la piste (centre, inclinaison réduite, corps = 1,05 × hauteur d'écran),
     ombre portée + halo de la marque. Rendu ~35 s/image : lancer Blender en arrière-plan et le Full HD des autres
     scènes en parallèle. Écrans d'interface en perspective jugés « bancals » : même redressement (rectangle vrai).
117. **Écran « l'IA fait le reste » : simulation vivante, pas une capture figée.** Bulle de demande, réponse qui
     s'écrit (curseur), carte « Génération de la vidéo… » avec spinner, pourcentage et barre qui montent, aperçu où les
     images du film se révèlent derrière une ligne de balayage ; tout piloté par la progression u du plan (0 → 1).
     Texte de phrase finale : montée douce en cascade (16 px, cubique) aux instants mesurés, ligne de base et graisse
     uniques, jamais les pistes y mesurées mot par mot (sauts de ligne de base).

118. **Le skill s'installe tout seul, entièrement, au premier usage.** Phase 0 = `python3 scripts/ensure_ready.py`,
     lancé par Claude sans rien demander : marqueur `.installed` + vérification rapide (`doctor.py --no-render`) → « PRÊT » ;
     sinon `install.sh` (Linux / macOS / WSL) ou `install.ps1` (Windows) installe outils système (apt / dnf / pacman /
     Homebrew / winget), modules Node, Chromium, modules Python, modèle faster-whisper et Blender 4.2 LTS portable dans
     `blender/app/` (archive Linux, .dmg macOS, .zip Windows), puis `doctor.py` avec rendu de test (Blender inclus).
     Jamais « installez Blender vous-même » : l'utilisateur ne doit rien faire, sauf un mot de passe sudo si exigé.

119. **Deux modes et règles à la demande : Claude décide seul, l'utilisateur ne dit jamais quoi appliquer.** Lire
     `references/essentials.md` (pas les 119 règles). Mode **Rapide** par défaut (mesure du mouvement des éléments clés,
     adaptation directe) ; mode **Studio** (décalque au pixel, règles 90-105) si copie exacte demandée OU si une scène
     échoue deux fois à `rhythm.py` / `style_compare.py` / `nervosity_audit.py`, et pour cette scène seulement. Les règles
     détaillées se chargent par sujet au moment où le déclencheur apparaît : `python3 scripts/rules.py 3d voix texte`
     (`--topics`, `--match mot`). Toute nouvelle règle est rangée dans un sujet de `scripts/rules.py`. Avant un long rendu :
     `render_estimate.py job.json` (Blender, carte graphique automatique : OptiX / CUDA / HIP / Metal / oneAPI, `MK_DEVICE=CPU`
     pour forcer le processeur) ou 1 s de film chronométrée ; annoncer la durée, puis rendre en arrière-plan.

120. **Installation robuste sur toutes les machines (leçon du test GitHub Linux / macOS / Windows).** (1) Python 3.9 à 3.13
     seulement : un Python trop récent (3.15 sur macOS) n'a pas encore les modules compilés (scipy, opencv) → l'installeur
     choisit 3.12 / 3.11 / 3.13 / 3.10, ou installe 3.12 (Homebrew, winget, sinon uv), et l'enregistre dans `.python`.
     (2) Chaque script commence par `import _mkpy` : il se relance avec ce Python si on l'a lancé avec un autre, et ajoute
     au PATH les dossiers des outils installés pendant la session (winget Links, Chocolatey, Homebrew, `blender/app`),
     qu'un terminal déjà ouvert ne voit pas encore ; `render.mjs` fait de même pour ffmpeg. (3) Toute modification de
     l'installation se valide par le test `.github/workflows/installation.yml` sur les trois systèmes.

121. **Pub « agent IA » (réf. Flows Agent) en mode Rapide : méthodes qui ont servi.** (1) Minutage relevé sur une planche
     dense (1 image / 0,5 s, `ffmpeg fps=2` + horodatage) + boîtes mesurées des 3 gestes clés (carte qui s'ouvre, zoom
     héros, vidéo plein écran) ajustées par `fit_easing` ; chaque scène du film garde ces instants. (2) Fond « peinture
     fluide » recréé en WebGL (bruit fbm à domaine déformé, palette de marque, grain), fonction de t. (3) Transformation
     d'image « aux couleurs du logo » : DEUX images de même cadrage (bleue / orange, la 2e faite par édition d'image chez
     l'utilisateur) révélées par un masque qui monte + nappe pastel floutée ; une simple rotation de teinte n'est
     acceptable que sans peau humaine. (4) Piège : un enfant en `visibility:visible` reste affiché même si sa scène est
     masquée → n'écrire que `inherit` / `hidden` sur les enfants. (5) Images manquantes : prompts fournis, emplacements
     `window.GEN` (gen.js) avec repli sur des images de l'utilisateur, pour avancer sans attendre. (6) Contrôle final de synchro
     OBLIGATOIRE avant le rendu : retranscrire la voix calée (faster-whisper, mots horodatés), lister chaque mot clé avec
     l'instant de SON élément à l'image, et recaler l'élément (jamais la voix) quand l'écart dépasse 0,15 s ; un élément
     ne doit pas apparaître avant son mot. Puis vérifier que chaque découpe de voix tombe dans un silence (< -40 dB sur
     30 ms à chaque bord) : zéro mot coupé. (7) Retour utilisatrice : cadre héros mesuré (80 % de la hauteur, coins ≈ 36 px)
     et carte de demande en verre dépoli (blanc 84 %, flou d'arrière-plan) qui chevauche l'image ; scènes d'interface
     sur fond blanc comme la référence ; aucune lueur ajoutée (aplats).

122. **Pub « nerveuse » : jamais de voix qui se chevauchent, jamais de temps mort (retour utilisatrice : « mou, mécanique,
     PowerPoint, les voix se mélangent »).** (1) Caler une voix découpée = placer les phrases À LA SUITE : début(n) ≥
     fin(n-1) + 0,08 s, vérifié par `assert` dans le script de calage, AVANT de chercher à poser chaque phrase sur son
     visuel ; ce sont les visuels qu'on recale sur les mots, jamais l'inverse. (2) Durée du film ≈ durée de la voix + 10-15 %
     (28,8 s de voix → 33,4 s, pas 48,7 s) : une table de tempo `KN` [temps scène, temps film] linéaire par morceaux joue
     les plans mesurés 1,5 à 2,8 fois plus vite là où il n'y a pas de voix, et ses nœuds posent chaque événement clé sur
     son mot ; `seek(T)` appelle `render(sceneT(T))`. (3) Caméra vivante : chaque scène entre avec un coup de zoom
     (1,07 → 1, expo, 0,28 s) puis pousse en continu (+1,8 %/s) ; flou de mouvement (`blurAt`) ± 0,12 s autour des coupes.
     (4) Lecteur simulé : bouton et minuteur en `flex:0 0 auto`, onde `min-width:0; overflow:hidden` (sinon bouton écrasé
     et minuteur qui déborde).

123. **INTERDIT CATÉGORIQUE : aucun effet sonore « par défaut » ni de banque toute faite.** Ni les préréglages de
     `sfx.py`, ni des sons génériques réutilisés d'un projet à l'autre : à chaque vidéo, Claude CONÇOIT une palette
     sonore neuve, propre au film (caractère, hauteur, longueur, grain réglés d'après les attaques mesurées dans la
     référence et le style de la marque), synthétisée en code (`sfx_premium.py` comme base de travail, à adapter :
     nouveaux timbres, nouvelles enveloppes, graine différente), puis l'annonce à l'utilisateur.
     **Effets sonores premium, recréés (retour utilisatrice : « pas d'effets sonores, les frappes et les vibrations de la
     référence sont excellentes »).** (1) Repérer QUAND la référence a des effets : composante percussive (HPSS) et
     attaques par bande (> 2,5 kHz = frappes, tics ; 30-150 Hz = impacts « vibration ») ; ne jamais les extraire (mêlés à
     la voix et à la musique, et ce sont ceux d'une autre marque) : on recrée leur caractère avec
     `scripts/sfx_premium.py` (key, tick, pop, whoosh, sub, shimmer, riser, select : doux, filtrés, jamais de bip).
     (2) Une liste d'effets calée image par image sur les événements du film, dans le temps du FILM : une frappe par
     caractère tapé (espaces plus doux), un cran par élément de roue, un pop par carte ou tuile, un sub sur chaque
     révélation, un souffle (whoosh) qui SE TERMINE sur la coupe. (3) Mixage : musique compressée par la voix, effets
     compressés par la voix (ratio 3) et posés au-dessus de la musique, puis -14 LUFS. (4) Mouvements « premium » :
     glisse douce (1,04 → 1 en 0,6 s, power2) plutôt qu'un coup sec, apparitions en fondu + légère échelle sans rebond,
     et les éléments d'une planche convergent en douceur vers leur dossier.

124. **Claude génère lui-même la voix off (moteur VoxStudio Pro : API Gemini TTS).** `scripts/voix_off.py`. Déroulé :
     (1) écrire le script UNE LIGNE PAR PLAN (règle 114), avec sa durée max ; le faire valider ; (2) clé : si le script
     répond `NO_KEY`, demander à l'utilisateur de lancer LUI-MÊME dans son terminal `python3 scripts/voix_off.py --set-key`
     (saisie masquée, fichier privé ~/.config/master-king-motion/gemini_api_key, droits 600) ou de définir GEMINI_API_KEY ;
     ne JAMAIS écrire une clé dans le projet, le dépôt ou un message ; si l'utilisateur colle sa clé dans la conversation,
     l'enregistrer dans ce fichier privé et lui conseiller de la renouveler ensuite dans Google AI Studio ;
     (3) `--check` (clé + modèles disponibles), puis `--script lignes.txt --out voix/ --voice <voix> --profile <profil>
     --style "<direction de jeu>"` : un WAV par ligne + manifest.json (durées) ; (4) retranscrire chaque fichier
     (faster-whisper) : texte exact, aucune consigne lue à voix haute ; régénérer seulement la ligne fautive ; une ligne
     trop longue pour son plan est raccourcie dans le texte, jamais accélérée au-delà de 1,08 ; (5) poser chaque fichier
     sur son plan À LA SUITE (règle 122 : ≥ 0,08 s entre deux lignes), recaler les visuels sur les mots, puis le contrôle
     final de synchro (règle 121). Modèle préféré gemini-3.8-flash-tts, repli automatique si Google le retire ; rotation
     entre plusieurs clés (GEMINI_API_KEYS) sur quota. Validé sur la pub « l'agent Master Skills » (voix Zephyr,
     profil tech_dynamic) : texte exact, 1,9-3,1 s par réplique, aucun découpage ni chevauchement à corriger.
