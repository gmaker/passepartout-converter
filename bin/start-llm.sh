#!/usr/bin/env bash
# Starts Ollama and downloads the vision model if the volume is still empty.
set -euo pipefail

# docker-compose.yml sits in the project root, one level above bin/.
cd "$(dirname "$0")/.."

if ! command -v docker >/dev/null 2>&1; then
    echo "Docker was not found in PATH."
    exit 1
fi

echo "Starting Ollama and downloading the vision model if needed."
echo "The first run pulls several gigabytes and can take a while."
echo

docker compose up -d ollama

# model-init exits once the model is in the shared volume.
docker compose up model-init

echo
echo "Ollama is running at http://localhost:11434"
echo "You can now run bin/run-passepartout.sh"
