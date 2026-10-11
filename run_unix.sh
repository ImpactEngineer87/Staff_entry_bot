#!/usr/bin/env sh
set -eu
cd -- "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
if [ ! -x .venv/bin/python ]; then
    echo "Install dependencies first. See README.md."
    exit 1
fi
exec .venv/bin/python main.py
