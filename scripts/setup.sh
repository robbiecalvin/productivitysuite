#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
python3 -c 'import sys; assert sys.version_info >= (3, 11), "Python 3.11+ is required"'
python3 -m venv .venv-desktop
.venv-desktop/bin/python -m pip install --require-hashes -r requirements-dev.lock
.venv-desktop/bin/python -c 'import requests, tkinter; assert tkinter.TkVersion >= 8.6, "Tk 8.6+ is required"; print("Python/Tk dependencies available")'
docker info --format '{{.ServerVersion}}'
