#!/usr/bin/env bash
# Installe Blender (LTS, portable, avec son propre Python) dans blender/app/, automatiquement, sans intervention.
# Linux : archive portable (+ bibliothèques système si besoin). macOS : image .dmg (Apple Silicon ou Intel).
# Windows : install.ps1 (archive .zip portable dans blender\app\).
# Résultat identique partout : blender/app/blender lance Blender.
# Usage : bash blender/install_blender.sh [version]     (défaut 4.2.3 LTS)   Vérif : blender/app/blender --version
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
V="${1:-4.2.3}"; MAJ="${V%.*}"
BASE="https://download.blender.org/release/Blender${MAJ}"
OS="$(uname -s)"; ARCH="$(uname -m)"
SUDO=""; [[ "$(id -u)" != "0" ]] && command -v sudo >/dev/null && SUDO="sudo"

if [[ -x "$HERE/app/blender" ]] && "$HERE/app/blender" --version >/dev/null 2>&1; then
  "$HERE/app/blender" --version | head -1; exit 0
fi
mkdir -p "$HERE/app"; TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

case "$OS" in
  Linux)
    [[ "$ARCH" == "x86_64" ]] || { echo "Blender portable n'existe qu'en x86_64 sous Linux (ici : $ARCH)"; exit 1; }
    URL="$BASE/blender-${V}-linux-x64.tar.xz"
    echo "téléchargement de Blender $V (≈ 350 Mo) : $URL"
    curl -fL --retry 4 -o "$TMP/b.tar.xz" "$URL"
    tar -xJf "$TMP/b.tar.xz" -C "$TMP"; cp -a "$TMP"/blender-*/. "$HERE/app/"
    if ! "$HERE/app/blender" --version >/dev/null 2>&1; then
      echo "installation des bibliothèques système de Blender"
      if command -v apt-get >/dev/null; then
        $SUDO apt-get update -qq || true
        $SUDO env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq libxi6 libxxf86vm1 libxfixes3 libxrender1 libgl1 libxkbcommon0 libsm6 libegl1 || true
      elif command -v dnf >/dev/null; then
        $SUDO dnf install -y -q libXi libXxf86vm libXfixes libXrender mesa-libGL libxkbcommon libSM mesa-libEGL || true
      elif command -v pacman >/dev/null; then
        $SUDO pacman -S --noconfirm --needed libxi libxxf86vm libxfixes libxrender mesa libxkbcommon libsm || true
      fi
    fi ;;
  Darwin)
    [[ "$ARCH" == "arm64" ]] && A="arm64" || A="x64"
    URL="$BASE/blender-${V}-macos-${A}.dmg"
    echo "téléchargement de Blender $V pour macOS $A (≈ 300 Mo) : $URL"
    curl -fL --retry 4 -o "$TMP/b.dmg" "$URL"
    MNT="$TMP/mnt"; mkdir -p "$MNT"
    hdiutil attach -nobrowse -quiet -mountpoint "$MNT" "$TMP/b.dmg"
    rm -rf "$HERE/app/Blender.app"; cp -R "$MNT/Blender.app" "$HERE/app/"
    hdiutil detach -quiet "$MNT" || true
    xattr -dr com.apple.quarantine "$HERE/app/Blender.app" 2>/dev/null || true
    ln -sf "$HERE/app/Blender.app/Contents/MacOS/Blender" "$HERE/app/blender" ;;
  MINGW*|MSYS*|CYGWIN*)
    echo "Windows : lancez install.ps1 (PowerShell), qui installe Blender dans blender\\app\\"; exit 1 ;;
  *) echo "système non pris en charge : $OS"; exit 1 ;;
esac

"$HERE/app/blender" --version | head -1
