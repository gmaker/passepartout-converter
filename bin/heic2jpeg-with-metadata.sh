#!/usr/bin/env bash
# Converts every .heic/.heif in input/ to JPEG, keeping the photographic metadata.
# The JPEG stays in input/ for the next step; the .heic moves to originals/.
set -uo pipefail

cd "$(dirname "$0")/.."

INPUT="$PWD/input"
ORIGINALS="$PWD/originals"
LOG="$PWD/heic2jpeg-errors.log"

mkdir -p "$INPUT" "$ORIGINALS"

for tool in ffmpeg exiftool; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "ERROR: $tool was not found in PATH."
        exit 1
    fi
done

ok=0
failed=0

# A name that stays free: photo.heic -> originals/photo.heic, photo_1.heic, ...
unique_original() {
    local name="$1"
    local base="${name%.*}"
    local extension="${name##*.}"
    local candidate="$ORIGINALS/$name"
    local counter=1

    while [ -e "$candidate" ]; do
        candidate="$ORIGINALS/${base}_${counter}.${extension}"
        counter=$((counter + 1))
    done

    printf '%s' "$candidate"
}

shopt -s nullglob nocaseglob

for input in "$INPUT"/*.heic "$INPUT"/*.heif; do
    name="$(basename "$input")"
    output="${input%.*}.jpg"

    if [ -e "$output" ]; then
        echo "SKIP: $name - JPEG already exists."
        continue
    fi

    echo "Converting: $name"

    if ! ffmpeg -hide_banner -loglevel error -y -i "$input" -frames:v 1 -q:v 1 "$output"; then
        echo "FAILED: $name"
        echo "FFmpeg failed: $input" >>"$LOG"
        rm -f "$output"
        failed=$((failed + 1))
        continue
    fi

    # Copy the photographic metadata and the ICC profile, but not Orientation:
    # FFmpeg has already rendered the pixels the right way up.
    if ! exiftool -overwrite_original \
        -TagsFromFile "$input" \
        -EXIF:All -XMP:All -IPTC:All -ICC_Profile \
        -Orientation= \
        "$output" >/dev/null 2>>"$LOG"; then
        echo "WARNING: JPEG created, but metadata copy failed."
        echo "ExifTool metadata copy failed: $input" >>"$LOG"
    fi

    destination="$(unique_original "$name")"

    if ! mv "$input" "$destination"; then
        echo "WARNING: JPEG created, but the original could not be moved."
        echo "Move failed: $input to $destination" >>"$LOG"
        failed=$((failed + 1))
        continue
    fi

    echo "OK: $name to $(basename "$output")"
    ok=$((ok + 1))
done

shopt -u nullglob nocaseglob

echo
echo "Done. Successful: $ok  Failed: $failed"
[ "$failed" -eq 0 ] || echo "See: $LOG"
