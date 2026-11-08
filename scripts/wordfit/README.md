# wordfit — décalque par ajustement de modèle (analyse par synthèse), écrit pendant le décalque lute (Master Skills)
Chaque mot est un gabarit Inter vivant ; à chaque image on ajuste corps, plume (x, ligne de base), flou directionnel
(sx, sy), opacité, angle pour minimiser l'écart avec l'alpha d'encre mesuré sur l'original (fond = plaque par image ou
aplat, encres w/m/d + encres colorées p/y/b + fond uni RVB). Les formes (pilules, panneaux, volets, disques) sont des
rectangles/disques ajustés de la même façon ; les traits libres sont vectorisés (vtrace.py) avec lueur mesurée.
- `fitlib.py` : rendu Inter (PIL), alpha d'encre, plaques, rect/disque ; CHEMIN PROJET : constante D en tête (à adapter)
- `track.py spec.json out.json` : suivi mesuré des mots (spec : id, text/runs, wght, opsz, ink, bg, key, range, box, clip)
- `vtrace.py sN id f0 f1 x,y,w,h --holes holes.json` : formes plates vectorisées image par image + lueur mesurée
- `build.py sN` (tracks/sN_build.json -> tracks/sN.js) puis `mkscene.py sN f0 f1` -> scenes/sN.html (moteur engine/mk-decal-lib.js)
- `s3_friends.py` : groupe rigide (pilule + lueur + texte) = base mesurée + affinité par image ; `s5_coins.py`/`s5_face.py` :
  pièces de verre (ellipse + dégradés mesurés + logo vectorisé)
Mesuré : textes 0,96-0,99 ; groupes rigides 0,91-0,95 ; pièces de verre 0,88-0,90 ; fouets très flous 0,8-0,9.
