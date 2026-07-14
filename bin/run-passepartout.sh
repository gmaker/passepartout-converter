#!/usr/bin/env bash
# Builds the passe-partouts from input/ and writes the .txt sidecars.
set -euo pipefail

cd "$(dirname "$0")/.."

if command -v python3 >/dev/null 2>&1; then
    PYTHON=python3
elif command -v python >/dev/null 2>&1; then
    PYTHON=python
else
    echo "Python was not found in PATH."
    exit 1
fi

if ! "$PYTHON" -c "import PIL" >/dev/null 2>&1; then
    echo "Installing Pillow..."
    "$PYTHON" -m pip install --upgrade Pillow
fi

"$PYTHON" src/passepartout_processor.py
