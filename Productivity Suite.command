#!/bin/zsh
cd "$(dirname "$0")" || exit 1

if [[ ! -x ".venv-desktop/bin/python" ]]; then
    echo "Desktop Python environment is missing."
    read "?Press Enter to close."
    exit 1
fi

exec .venv-desktop/bin/python -m suite.desktop_preview
