# Demander des visuels à l'utilisateur (prompts)

L'utilisateur génère images et vidéos avec ses propres outils (Midjourney, Flux, Ideogram, Kling, Runway, Veo,
Sora…). Claude écrit des prompts **précis et prêts à copier** quand un visuel ne peut pas être fait proprement en
code : objet 3D photoréaliste, décor, personnage, prise de vue réelle, texture riche.

## Ce qui se fait en code (ne pas demander)
Typographie, formes, cartes et UI d'app reconstruites, icônes simples, téléphone 3D (`mk-phone.js`), dégradés,
blobs lumineux, grilles, particules, transitions, compteurs, curseur, graphiques.

## Format d'une demande
Pour chaque visuel, donner :
1. **Rôle** dans la vidéo : scène, durée à l'écran, mouvement qu'il subira (on l'anime nous-mêmes).
2. **Prompt** (en anglais, c'est plus fiable), selon cette structure :
   `[sujet précis], [matière / finition], [éclairage], [cadrage et angle], [fond], [palette HEX de la marque], [style de rendu], [contraintes]`
3. **Spécifications** :
   - image : 2048 px minimum, PNG ;
   - fond : uni (ou transparent si l'outil le permet), à détourer ;
   - vidéo : 4 à 6 s, 24 ou 30 i/s, caméra fixe ou mouvement imposé, sans texte, sans logo ;
   - même éclairage pour toute la série.
4. **Prompt négatif** si l'outil l'accepte : `text, watermark, logo, extra fingers, distorted, low-res, blurry`.

## Modèles
- **Objet 3D héros** (cadenas, carte, pièce, icône 3D) :
  `a glossy 3D [object] icon, soft matte plastic with subtle subsurface glow, studio softbox lighting from top-left, centered, 3/4 view, isolated on plain #F4F1EA background, brand colors #FFCC00 and #004F71, Octane render, ultra clean, no text`
- **Téléphone photoréaliste** (si la référence en montre un en vrai 3D) :
  `a modern smartphone, ultra thin bezels, [color] titanium frame, floating at a slight 20° tilt, screen fully black and blank (we will insert the UI), soft studio light, gentle contact shadow, plain [HEX] background, photoreal product render, 8k`
  Écran **noir uni** : l'UI est incrustée ensuite (suivi des 4 coins avec `track_quad.py` sur une vidéo, ou plaquée sur une image).
- **Vidéo d'objet qui tourne** :
  `slow 180° turntable rotation of [object], locked-off camera, seamless plain [HEX] background, soft studio lighting, 5 seconds, no camera shake, no text`
- **Décor** (fond de scène) :
  `[lieu / ambiance] wide shot, soft depth of field, [heure / lumière], color graded toward [HEX palette], empty space in the center for UI overlay, cinematic, no people, no text`
- **Personnage / scène de vie** (marché, étudiant, commerçante…) : décrire lieu, tenue, action, lumière, cadrage,
  et demander de la place libre pour le texte.

## Intégration
Détourage (`rembg` si installé, ou fond uni → clé), étalonnage vers la palette (`brand.map`). Le mouvement vient de
l'ADN de la référence (entrée, flottement, rotation mesurés), et on ajoute l'ombre et la lumière cohérentes avec la scène.
