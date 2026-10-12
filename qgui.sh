#!/usr/bin/env sh
# Spustenie Quarto Studio: ./qgui.sh [PRIEČINOK]
DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHONPATH="$DIR${PYTHONPATH:+:$PYTHONPATH}" exec python3 -m qgui "$@"
