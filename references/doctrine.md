# Doctrine : ce qui sépare un rendu de studio d'un rendu « fait par une IA »

## Ce qui trahit une vidéo générée (à ne jamais laisser passer)
1. **Eases par défaut** : `power1.out` / `power2.out` partout, durées rondes (0,5 s, 1 s). Un studio utilise 3 à 5
   courbes différentes, avec des durées au 1/30 s près. → Les eases et durées viennent de l'ADN.
2. **Tout bouge en même temps** : pas de chevauchement. → Décalages mesurés (stagger, `motif`), entrées qui
   commencent avant la fin de la précédente.
3. **Mouvement sans poids** : linéaire, sans anticipation ni stabilisation. → Reprendre le dépassement mesuré
   (`overshoot_px`) et les `back`/`expo` de la référence, pas plus.
4. **Coupes hors temps** : les coupes et les impacts tombent sur les temps de la musique de l'utilisateur, à l'image près.
5. **Pauses mortes** : plus de 2,5 s figées, alors que la référence vit (dérive lente, lumière). → Mouvement secondaire
   continu en temps réel (`frame(tn)`), avec la vitesse mesurée.
6. **Textes plantés au milieu** : la composition de la référence (positions normalisées, grille) est respectée. Un
   texte plus long est réduit dans SA boîte, il ne déborde jamais.
7. **Polices système, crénelage, textes flous** : vraies polices, rendu net, échelle typographique de la référence
   (`MK.refFontSize`).
8. **Couleurs plates « web »** : on garde le rythme clair / sombre / accent de la référence via `brand.map`, avec les
   dégradés, ombres douces et lumières qu'elle a.
9. **Finition absente ou en trop** : grain, flou de mouvement, vignettage uniquement s'ils sont mesurés dans la
   référence, avec ses valeurs (`dissect.json → finish`).
10. **Son plat** : voix intelligible (musique baissée sous la voix), -14 LUFS, crête vraie ≤ -1 dBTP, fin de musique en
    fondu calée sur la dernière image.

## Règles de construction
- Une timeline par scène, tout en fonction du temps. Le rendu image par image doit pouvoir sauter à n'importe quel instant.
- Seulement des transformations (x, y, scale, rotation, opacity) : pas de left/top animés.
- Masques de texte : marge interne contre les lettres coupées. `immediateRender: false` sur les `fromTo` en timeline.
- Mouvements à vitesse constante (rotation, défilement, parallaxe) : en temps réel de la nouvelle vidéo (`frame(tn)`),
  jamais étirés.
- Mouvements proportionnels (barre de progression, compteur) : dans la timeline, ils suivent l'étirement.
- Téléphone et écrans d'app :
  - écrans reconstruits pièce par pièce (cartes, icônes, chiffres qui comptent, curseur ou doigt qui tape) ;
  - données personnelles remplacées ;
  - barre d'état recréée (heure 9:41, réseau, batterie) ;
  - reflet de verre animé (`ph.light`).
- Transitions : sortie en `.in`, entrée en `.out`, vitesses raccordées. Un fondu enchaîné ou un volet garde la scène
  sortante visible (`overlap_out`).

## Contrôle à l'œil (en plus des scripts)
- Côte à côte en entier, puis image par image sur chaque transition.
- Planche de 20 images : textes coupés, chevauchements, marges, couleurs exactes de la marque (pipette).
- Écoute au casque : voix, coupes sur les temps, fin.
