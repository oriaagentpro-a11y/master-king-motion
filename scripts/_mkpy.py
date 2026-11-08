"""Bootstrap imported first by every script: the right Python, and freshly installed tools on the PATH.

1. Interpreter: install.sh / install.ps1 record in <skill>/.python the Python 3.9-3.13 they installed the modules
   into (a brand-new system Python, e.g. 3.15, may have no wheels for scipy / opencv). If the script was started
   with another interpreter ("python3 scripts/x.py"), it is relaunched with the recorded one, transparently.
2. PATH: tools installed during THIS session (winget, Chocolatey, Homebrew, the skill's Blender) are not yet on the
   PATH of an already open terminal / Claude Code session; their usual folders are prepended here.
"""
import os, sys, subprocess

for _st in (sys.stdout, sys.stderr):   # accents lisibles partout (la console Windows est en cp1252 par défaut)
    try:
        _st.reconfigure(encoding='utf-8', errors='replace')
    except Exception:  # noqa: BLE001
        pass
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_extra = [os.path.join(_ROOT, 'blender', 'app')]
if os.name == 'nt':
    la = os.environ.get('LOCALAPPDATA', ''); pf = os.environ.get('ProgramFiles', r'C:\Program Files')
    _extra += [os.path.join(la, 'Microsoft', 'WinGet', 'Links'), r'C:\ProgramData\chocolatey\bin',
               os.path.join(pf, 'nodejs'), os.path.join(pf, 'Git', 'cmd')]
else:
    _extra += ['/opt/homebrew/bin', '/usr/local/bin', os.path.expanduser('~/.local/bin')]
_path = os.environ.get('PATH', '').split(os.pathsep)
os.environ['PATH'] = os.pathsep.join([d for d in _extra if os.path.isdir(d) and d not in _path] + _path)

_rec = os.path.join(_ROOT, '.python')
if os.path.exists(_rec) and not os.environ.get('MKPY_RELAUNCHED'):
    _py = open(_rec, encoding='utf-8').read().strip()
    if _py and os.path.exists(_py) and os.path.realpath(_py) != os.path.realpath(sys.executable):
        os.environ['MKPY_RELAUNCHED'] = '1'
        _args = [_py, os.path.abspath(sys.argv[0])] + sys.argv[1:]
        if os.name == 'nt':
            sys.exit(subprocess.call(_args))
        os.execv(_py, _args)
