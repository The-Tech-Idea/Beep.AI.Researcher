#!/usr/bin/env python3
"""Beep.AI.Researcher launcher — venv + deps + run."""
import os
import sys
import subprocess
import platform
from pathlib import Path


def get_venv_python():
    venv = Path('.venv')
    if platform.system() == 'Windows':
        py = venv / 'Scripts' / 'python.exe'
    else:
        py = venv / 'bin' / 'python'
    return py if py.exists() else None


def setup_venv():
    venv_py = get_venv_python()
    if venv_py:
        return str(venv_py)
    print('Creating .venv...')
    subprocess.run([sys.executable, '-m', 'virtualenv', '.venv'], check=True, capture_output=True)
    return str(get_venv_python())


def install_deps(venv_python):
    req = Path('requirements.txt')
    if not req.exists():
        return
    print('Installing dependencies...')
    subprocess.run([venv_python, '-m', 'pip', 'install', '-r', 'requirements.txt', '-q'],
                   check=True, capture_output=True)


def main():
    os.chdir(Path(__file__).parent)
    venv_py = setup_venv()
    install_deps(venv_py)
    print('Starting Beep.AI.Researcher...')
    try:
        subprocess.run([venv_py, 'run.py'] + sys.argv[1:], check=False)
    except KeyboardInterrupt:
        # Ctrl+C is forwarded to the child (run.py/Flask) which handles it
        # gracefully. Suppress the traceback here so the exit is clean.
        pass


if __name__ == '__main__':
    main()
