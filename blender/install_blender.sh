#!/usr/bin/env bash
# Installe Blender (LTS, portable, avec son propre Python) dans blender/app/ — pour le rendu 3D photoréaliste (Cycles).
# Usage : bash blender/install_blender.sh [version]     (défaut 4.2.3 LTS)   Vérif : blender/app/blender --version
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
V="${1:-4.2.3}"; MAJ="${V%.*}"
OS="$(uname -s)"
if [[ -x "$HERE/app/blender" ]]; then "$HERE/app/blender" --version | head -1; exit 0; fi
case "$OS" in
  Linux)  URL="https://download.blender.org/release/Blender${MAJ}/blender-${V}-linux-x64.tar.xz" ;;
  Darwin) echo "macOS : installer Blender ${V} depuis https://www.blender.org/download/ puis : ln -s /Applications/Blender.app/Contents/MacOS/Blender $HERE/app/blender"; exit 1 ;;
  *)      echo "Windows : installer Blender ${V} (blender.org) puis définir BLENDER=chemin\\blender.exe"; exit 1 ;;
esac
mkdir -p "$HERE/app"; TMP="$(mktemp -d)"
echo "téléchargement $URL"; curl -fL --retry 4 -o "$TMP/b.tar.xz" "$URL"
tar -xJf "$TMP/b.tar.xz" -C "$TMP"; cp -a "$TMP"/blender-*/. "$HERE/app/"; rm -rf "$TMP"
# headless libs (Debian/Ubuntu) if missing
if ! "$HERE/app/blender" --version >/dev/null 2>&1; then
  echo "bibliothèques système manquantes : sudo apt-get install -y libxi6 libxxf86vm1 libxfixes3 libxrender1 libgl1 libxkbcommon0 libsm6"; exit 1; fi
"$HERE/app/blender" --version | head -1
