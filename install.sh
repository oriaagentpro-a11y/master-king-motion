#!/usr/bin/env bash
# Installation COMPLÈTE et automatique de master-king-motion (Linux, macOS, WSL). Aucune question posée.
# Installe tout ce qu'il faut pour réellement travailler :
#   outils système (Node.js, Python, FFmpeg, git) si absents, modules Node (GSAP, Three.js, Playwright),
#   Chromium, modules Python (mesure, audio, transcription), modèle de transcription de la voix,
#   Blender 4.2 LTS (3D Cycles), puis diagnostic avec rendu de test.
#   bash install.sh            installe tout (ne refait pas ce qui est déjà là)
#   bash install.sh --check    vérifie seulement
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OS="$(uname -s)"
SUDO=""; [[ "$(id -u)" != "0" ]] && command -v sudo >/dev/null && SUDO="sudo"
step() { printf '\n== %s ==\n' "$1"; }

pkg_install() {   # pkg_install <nom apt> <nom dnf> <nom pacman> <nom brew>
  if [[ "$OS" == "Darwin" ]]; then
    if ! command -v brew >/dev/null; then
      echo "installation de Homebrew"
      NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
      eval "$(/opt/homebrew/bin/brew shellenv 2>/dev/null || /usr/local/bin/brew shellenv)"
    fi
    brew install "$4"
  elif command -v apt-get >/dev/null; then
    $SUDO apt-get update -qq || true; $SUDO env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq $1
  elif command -v dnf >/dev/null; then $SUDO dnf install -y -q $2
  elif command -v pacman >/dev/null; then $SUDO pacman -S --noconfirm --needed $3
  else echo "gestionnaire de paquets introuvable : installez $4 à la main"; return 1; fi
}

node_ok() { command -v node >/dev/null && [[ "$(node -p 'process.versions.node.split(".")[0]')" -ge 18 ]]; }
py_find() { for p in "${PYTHON:-}" python3 python; do [[ -n "$p" ]] && command -v "$p" >/dev/null \
  && "$p" -c 'import sys; sys.exit(sys.version_info < (3, 9))' 2>/dev/null && { echo "$p"; return; }; done; }

if [[ "${1:-}" != "--check" ]]; then
  step "Outils système"
  command -v git  >/dev/null || pkg_install git git git git
  command -v curl >/dev/null || pkg_install curl curl curl curl
  command -v ffmpeg >/dev/null || pkg_install ffmpeg ffmpeg ffmpeg ffmpeg
  [[ -n "$(py_find)" ]] || pkg_install "python3 python3-pip python3-venv" "python3 python3-pip" "python python-pip" python@3.12
  if ! node_ok; then
    if [[ "$OS" == "Linux" ]] && command -v apt-get >/dev/null; then
      curl -fsSL https://deb.nodesource.com/setup_20.x | $SUDO -E bash - && $SUDO apt-get install -y -qq nodejs
    else pkg_install nodejs nodejs nodejs node; fi
  fi
  PY="$(py_find)"; [[ -n "$PY" ]] || { echo "Python 3.9+ introuvable après installation"; exit 1; }
  node_ok || { echo "Node.js 18+ introuvable après installation"; exit 1; }
  echo "Node $(node -v) · $($PY --version) · $(ffmpeg -version | head -1 | cut -d' ' -f1-3)"

  step "Moteur de rendu (Node : GSAP, Three.js, Playwright)"
  (cd "$HERE/engine" && npm install --no-audit --no-fund)

  step "Outils d'analyse (Python)"
  "$PY" -m pip install -q -r "$HERE/requirements.txt" 2>/dev/null \
    || "$PY" -m pip install -q --break-system-packages -r "$HERE/requirements.txt" \
    || "$PY" -m pip install -q --user -r "$HERE/requirements.txt"

  step "Chromium (rendu et mesures)"
  if [[ -z "${CHROME_PATH:-}" ]]; then
    if [[ "$OS" == "Linux" && ( -z "$SUDO" || "$(id -u)" == "0" || -n "$(sudo -n true 2>/dev/null && echo y)" ) ]]; then
      (cd "$HERE/engine" && $SUDO npx --yes playwright install --with-deps chromium) \
        || (cd "$HERE/engine" && npx --yes playwright install chromium)
    else
      (cd "$HERE/engine" && npx --yes playwright install chromium)
    fi
  fi

  step "Modèle de transcription de la voix (faster-whisper, calage mot à mot)"
  "$PY" -c "import os; from faster_whisper import WhisperModel; WhisperModel(os.environ.get('MK_WHISPER','small'), device='cpu', compute_type='int8'); print('modèle prêt')" \
    || echo "(modèle non téléchargé : il le sera au premier calage de voix)"

  step "Blender 4.2 LTS (3D photoréaliste, Cycles)"
  bash "$HERE/blender/install_blender.sh"
fi

step "Diagnostic"
PY="$(py_find)"
"$PY" "$HERE/scripts/doctor.py" && date -u +%FT%TZ > "$HERE/.installed"
