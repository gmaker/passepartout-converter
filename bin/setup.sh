#!/usr/bin/env bash
# First run: installs everything the pipeline needs.
# Already-installed tools are left alone.
set -uo pipefail

cd "$(dirname "$0")/.."

if command -v apt-get >/dev/null 2>&1; then
    INSTALL="sudo apt-get install -y"
    PKG_EXIFTOOL="libimage-exiftool-perl"
    PKG_FFMPEG="ffmpeg"
    PKG_PYTHON="python3 python3-pip"
    sudo apt-get update
elif command -v dnf >/dev/null 2>&1; then
    INSTALL="sudo dnf install -y"
    PKG_EXIFTOOL="perl-Image-ExifTool"
    PKG_FFMPEG="ffmpeg"
    PKG_PYTHON="python3 python3-pip"
elif command -v pacman >/dev/null 2>&1; then
    INSTALL="sudo pacman -S --noconfirm"
    PKG_EXIFTOOL="perl-image-exiftool"
    PKG_FFMPEG="ffmpeg"
    PKG_PYTHON="python python-pip"
elif command -v brew >/dev/null 2>&1; then
    INSTALL="brew install"
    PKG_EXIFTOOL="exiftool"
    PKG_FFMPEG="ffmpeg"
    PKG_PYTHON="python"
else
    echo "No supported package manager found (apt, dnf, pacman, brew)."
    echo "Install by hand: python3, exiftool, ffmpeg, docker."
    exit 1
fi

install_if_missing() {
    local command_name="$1"
    local packages="$2"
    local title="$3"

    if command -v "$command_name" >/dev/null 2>&1; then
        echo "[ok] $title is already installed."
        return
    fi

    echo
    echo "Installing $title ..."
    # shellcheck disable=SC2086
    $INSTALL $packages || echo "WARNING: $title could not be installed automatically."
}

echo "FFmpeg is only needed for HEIC photos, Docker only for the descriptions."

install_if_missing python3  "$PKG_PYTHON"   "Python"
install_if_missing exiftool "$PKG_EXIFTOOL" "ExifTool"
install_if_missing ffmpeg   "$PKG_FFMPEG"   "FFmpeg"

echo
echo "Installing Pillow..."
python3 -m pip install --upgrade Pillow || echo "WARNING: Pillow could not be installed."

if ! command -v docker >/dev/null 2>&1; then
    echo
    echo "Docker was not found. It is only needed for the descriptions and hashtags."
    echo "Install it from https://docs.docker.com/engine/install/ and add yourself to the docker group."
fi

echo
echo "Done. Put your photos into input/ and run bin/run-all.sh"
