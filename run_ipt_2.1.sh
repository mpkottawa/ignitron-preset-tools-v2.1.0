#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$SCRIPT_DIR"

if command -v python3 >/dev/null 2>&1; then
    PYTHON=python3
elif command -v python >/dev/null 2>&1; then
    PYTHON=python
else
    printf '%s\n' "Python 3 was not found. Install Python 3.10 or newer, then try again." >&2
    exit 1
fi

exec "$PYTHON" "$SCRIPT_DIR/ignitron_preset_tools_v2.1.py" "$@"
