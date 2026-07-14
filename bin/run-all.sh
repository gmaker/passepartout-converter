#!/usr/bin/env bash
# The whole pipeline: start the LLM, convert HEIC, build the passe-partouts.
# Put your photos into input/ in the project root, then run this.
set -uo pipefail

BIN="$(cd "$(dirname "$0")" && pwd)"
cd "$BIN/.."

mkdir -p input

skip_llm=""

if ! command -v docker >/dev/null 2>&1; then
    echo "Docker was not found in PATH - continuing without descriptions and hashtags."
    skip_llm=1
fi

if [ -z "$skip_llm" ]; then
    echo "[1/3] Starting the local LLM. The first run downloads about 6 GB."

    if ! docker compose up -d ollama; then
        echo "Ollama could not be started - continuing without descriptions and hashtags."
        skip_llm=1
    # Pulls the model if the volume is empty, exits immediately otherwise.
    elif ! docker compose up model-init; then
        echo "The model could not be downloaded - continuing without descriptions and hashtags."
        skip_llm=1
    fi
fi

if [ -n "$skip_llm" ]; then
    echo
    echo "The .txt files will hold the camera metadata only."
fi

echo
echo "[2/3] Converting HEIC files, if there are any."

shopt -s nullglob nocaseglob
heic_files=(input/*.heic input/*.heif)
shopt -u nullglob nocaseglob

if [ ${#heic_files[@]} -gt 0 ]; then
    "$BIN/heic2jpeg-with-metadata.sh"
else
    echo "No HEIC files found - skipping."
fi

echo
echo "[3/3] Building the passe-partouts."
"$BIN/run-passepartout.sh"

echo
echo "All done. Look into processed/"
