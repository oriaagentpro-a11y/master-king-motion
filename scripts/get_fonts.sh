#!/usr/bin/env bash
# Polices candidates (licences libres uniquement : OFL, Apache, UFL), pour font_search.py et pour les films.
# Usage : bash get_fonts.sh [--essentials] [dest_dir]
#   --essentials   ≈ 30 familles très courantes en motion design (≈ 60 Mo), installé automatiquement par install.sh
#   (sans option)  tout le catalogue Google Fonts (≈ 1 Go)
# Destination par défaut : ~/.cache/reverse-motion/google-fonts
set -euo pipefail
ESS=0; [[ "${1:-}" == "--essentials" ]] && { ESS=1; shift; }
DEST="${1:-$HOME/.cache/reverse-motion/google-fonts}"
FAMS="inter poppins montserrat roboto opensans lato oswald raleway playfairdisplay dmsans spacegrotesk manrope
plusjakartasans sora bebasneue anton archivo worksans rubik nunito urbanist outfit syne unbounded lexend
barlow figtree onest instrumentsans dmserifdisplay"
if [[ ! -d "$DEST/.git" ]]; then
  mkdir -p "$(dirname "$DEST")"
  git clone -q --depth 1 --filter=blob:none --sparse https://github.com/google/fonts.git "$DEST"
fi
cd "$DEST"
if [[ $ESS == 1 ]]; then
  if [[ "$(git sparse-checkout list 2>/dev/null | head -1)" != "ofl" ]]; then
    git sparse-checkout set $(for f in $FAMS; do printf 'ofl/%s ' "$f"; done)
  fi
else
  git sparse-checkout set ofl apache ufl
fi
git pull -q --depth 1 2>/dev/null || true
echo "Polices candidates dans : $DEST ($(find "$DEST" -name '*.ttf' | wc -l) fichiers .ttf)"
