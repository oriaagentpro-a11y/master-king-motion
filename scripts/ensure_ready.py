"""Make sure master-king-motion can REALLY work on this machine, installing whatever is missing. No question asked.

Claude runs this itself at the start of every job (phase 0), before anything else:
    python3 scripts/ensure_ready.py
- Fast path: if the install marker exists and the quick check passes, prints "PRÊT" and exits 0 (a few seconds).
- Otherwise runs the full installer for this OS (install.sh on Linux / macOS / WSL, install.ps1 on Windows):
  system tools (Node, Python, FFmpeg, git), Node modules, Chromium, Python modules, voice model, Blender 4.2 LTS,
  then the doctor with a test render. Exit 0 = ready, 1 = something could not be installed (the log says what).
Options: --force (reinstall / re-check everything), --check (never install, only report).
"""
import os as _o, sys as _s; _s.path.insert(0, _o.path.dirname(_o.path.abspath(__file__))); import _mkpy  # noqa: E401,E702,F401  (bon Python + PATH)
import os, sys, subprocess, platform

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MARK = os.path.join(ROOT, '.installed')


def quick_ok():
    r = subprocess.run([sys.executable, os.path.join(HERE, 'doctor.py'), '--no-render'], capture_output=True, text=True)
    return r.returncode == 0, r.stdout


def main():
    force, check = '--force' in sys.argv, '--check' in sys.argv
    if not force and os.path.exists(MARK):
        ok, out = quick_ok()
        if ok:
            print('PRÊT : master-king-motion est entièrement installé.'); return 0
        print(out)
    if check:
        ok, out = quick_ok(); print(out); return 0 if ok else 1
    print('Installation complète de master-king-motion (une seule fois, 5 à 15 min selon la connexion)…', flush=True)
    if platform.system() == 'Windows':
        cmd = ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', os.path.join(ROOT, 'install.ps1')]
    else:
        cmd = ['bash', os.path.join(ROOT, 'install.sh')]
    r = subprocess.run(cmd, stdin=subprocess.DEVNULL)
    if r.returncode == 0 and os.path.exists(MARK):
        print('PRÊT : tout est installé et le rendu de test a réussi.'); return 0
    print('ÉCHEC : voir les lignes MANQUANT ci-dessus (souvent un mot de passe administrateur demandé par sudo).')
    return 1


if __name__ == '__main__':
    sys.exit(main())
