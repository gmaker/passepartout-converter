#!/usr/bin/env python3
"""
Instagram passe-partout processor.

Workflow:
1. Reads supported images from ../input
2. Reads camera metadata with ExifTool.
3. Creates a 1080x1350 white canvas.
4. Fits the image without cropping.
5. Adds a centered metadata caption below the image.
6. Asks a local vision LLM (Ollama, see docker-compose.yml) for a description
   and hashtags, and writes them next to the export as a .txt sidecar.
7. Saves the result to ./processed
8. Moves the original to ./originals only after a successful export.

HEIC/HEIF:
Use heic2jpeg.bat first, unless Pillow on your system has HEIC support.
"""

from __future__ import annotations

import base64
import io
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from PIL import Image, ImageCms, ImageDraw, ImageFilter, ImageFont, ImageOps

# =========================
# User settings
# =========================

CANVAS_W = 1080
CANVAS_H = 1350

# Layouts are selected automatically after EXIF orientation is applied.
# Landscape images get narrower side margins so they stay large on a phone.
PORTRAIT_LAYOUT = {
    "left": 90,
    "right": 90,
    "top": 90,
    "bottom": 185,
    "vertical_align": "center",
    "y_offset": 0,
}

LANDSCAPE_LAYOUT = {
    "left": 50,
    "right": 50,
    "top": 95,
    "bottom": 220,
    "vertical_align": "center",
    "y_offset": -28,
}

SQUARE_LAYOUT = {
    "left": 70,
    "right": 70,
    "top": 100,
    "bottom": 205,
    "vertical_align": "center",
    "y_offset": -10,
}

# Images whose width/height ratio is close to 1 are treated as square.
SQUARE_RATIO_MIN = 0.90
SQUARE_RATIO_MAX = 1.10

BACKGROUND = (255, 255, 255)
TEXT_COLOR = (20, 20, 20)

FONT_SIZE = 28
CAPTION_TOP_GAP = 26

JPEG_QUALITY = 97
JPEG_SUBSAMPLING = 0  # 4:4:4

# Gentle output sharpening after downsizing.
SHARPEN_ENABLED = True
SHARPEN_RADIUS = 0.6
SHARPEN_PERCENT = 70
SHARPEN_THRESHOLD = 2

# Convert embedded ICC profiles to sRGB and embed an sRGB profile in output.
COLOR_MANAGEMENT_ENABLED = True

# Use mozjpeg's cjpeg automatically when available in PATH.
# Pillow remains the fallback, so the script works without mozjpeg.
USE_MOZJPEG_IF_AVAILABLE = True

STRIP_OUTPUT_METADATA = True  # removes EXIF/GPS; sRGB ICC is still preserved

SUPPORTED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"
}

# =========================
# Caption sidecar (local LLM)
# =========================

# Writes <name>_passepartout.txt next to every exported image:
# description, blank line, camera metadata, blank line, hashtags.
# Requires a local Ollama with a vision model: docker compose up -d
# If the LLM is unreachable, the sidecar still gets the metadata line.
SIDECAR_ENABLED = True

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("PASSEPARTOUT_MODEL", "qwen2.5vl:7b")

LLM_TIMEOUT_SECONDS = 180
LLM_TEMPERATURE = 0.6

# The photo is downscaled before it is sent to the model.
LLM_PREVIEW_MAX_SIDE = 1024
LLM_PREVIEW_QUALITY = 85

# The prompt, the language of the description and the mandatory hashtags all live
# in config.json in the project root. The model picks a genre from its "genres"
# keys; that set plus "always" is merged with the tags the model came up with.
CONFIG_FILE_NAME = "config.json"

# Used when config.json is missing or a key is not set.
DEFAULT_LANGUAGE = "English"

DEFAULT_PROMPT = [
    "You are writing an Instagram caption for a photographer's shot.",
    "Look at the photo and answer with JSON only.",
    "- description: one short evocative sentence in {language} about what is happening "
    "in the frame and its mood. No hashtags, no quotes, no camera talk. "
    "Maximum 90 characters.",
    "- hashtags: {min} to {max} English hashtags, lowercase, no '#' sign, no spaces "
    "inside a tag. Skip the obvious genre words - describe the mood, the light, "
    "the subject and the season instead.",
    "- genre: the single best match for this photo from this list: {genres}. "
    "Use 'other' only when nothing fits.",
]

# How many tags to ask the model for, on top of the mandatory ones.
HASHTAGS_MIN = 5
HASHTAGS_MAX = 8

# Hard ceiling for the whole list. Mandatory tags are never dropped —
# the model's own tags are cut first if the list gets too long.
HASHTAGS_TOTAL_MAX = 15
HASHTAGS_PER_LINE = 3

SIDECAR_EXTENSION = ".txt"

# All of these live in the project root, one level above this script.
INPUT_DIR_NAME = "input"
PROCESSED_DIR_NAME = "processed"
ORIGINALS_DIR_NAME = "originals"
ERROR_LOG_NAME = "process-errors.log"

# =========================


def project_root() -> Path:
    """The folder above src/ — it holds input/, processed/, originals/ and config.json."""
    return Path(__file__).resolve().parent.parent


def find_exiftool() -> str:
    executable = shutil.which("exiftool")
    if not executable:
        raise RuntimeError(
            "ExifTool was not found in PATH. Open a new terminal and run: exiftool -ver"
        )
    return executable


def read_metadata(exiftool: str, image_path: Path) -> dict[str, Any]:
    fields = [
        "-CameraModelName",
        "-Model",
        "-LensModel",
        "-Lens",
        "-FocalLength",
        "-FocalLengthIn35mmFormat",
        "-FNumber",
        "-Aperture",
        "-ExposureTime",
        "-ShutterSpeed",
        "-ISO",
        "-DateTimeOriginal",
        "-Orientation",
    ]

    command = [
        exiftool,
        "-json",
        "-n",
        *fields,
        str(image_path),
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "ExifTool failed")

    data = json.loads(result.stdout)
    return data[0] if data else {}


def first_present(meta: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = meta.get(key)
        if value not in (None, "", 0):
            return value
    return None


def format_number(value: Any, decimals: int = 1) -> str | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if abs(number - round(number)) < 0.001:
        return str(int(round(number)))

    return f"{number:.{decimals}f}".rstrip("0").rstrip(".")


def format_exposure(value: Any) -> str | None:
    if value in (None, ""):
        return None

    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned:
            return cleaned

    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return None

    if seconds <= 0:
        return None

    if seconds >= 1:
        return f"{format_number(seconds, 1)}s"

    denominator = round(1 / seconds)
    if denominator > 0:
        return f"1/{denominator}s"

    return f"{seconds:.3f}s"


def build_caption(meta: dict[str, Any]) -> str:
    parts: list[str] = []

    focal_35 = first_present(meta, "FocalLengthIn35mmFormat")
    focal = focal_35 if focal_35 is not None else first_present(meta, "FocalLength")
    focal_text = format_number(focal, 1)
    if focal_text:
        parts.append(f"{focal_text}mm")

    aperture = first_present(meta, "FNumber", "Aperture")
    aperture_text = format_number(aperture, 1)
    if aperture_text:
        parts.append(f"f/{aperture_text}")

    exposure = first_present(meta, "ExposureTime", "ShutterSpeed")
    exposure_text = format_exposure(exposure)
    if exposure_text:
        parts.append(exposure_text)

    iso = first_present(meta, "ISO")
    iso_text = format_number(iso, 0)
    if iso_text:
        parts.append(f"ISO {iso_text}")

    return "   ·   ".join(parts) if parts else " "


def find_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path(r"C:\Windows\Fonts\times.ttf"),
        Path(r"C:\Windows\Fonts\timesbd.ttf"),
        Path(r"C:\Windows\Fonts\arial.ttf"),
        Path(r"C:\Windows\Fonts\calibri.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]

    for font_path in candidates:
        if font_path.exists():
            try:
                return ImageFont.truetype(str(font_path), size=size)
            except OSError:
                continue

    return ImageFont.load_default()


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path

    counter = 1
    while True:
        candidate = path.with_name(f"{path.stem}_{counter}{path.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def choose_layout(width: int, height: int) -> tuple[str, dict[str, Any]]:
    if height <= 0:
        raise ValueError("Image height must be greater than zero")

    ratio = width / height

    if SQUARE_RATIO_MIN <= ratio <= SQUARE_RATIO_MAX:
        return "square", SQUARE_LAYOUT

    if width > height:
        return "landscape", LANDSCAPE_LAYOUT

    return "portrait", PORTRAIT_LAYOUT


def fit_image(image: Image.Image, max_w: int, max_h: int) -> Image.Image:
    copy = image.copy()
    original_size = copy.size
    copy.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)

    # Sharpen only when the image was actually reduced.
    if SHARPEN_ENABLED and copy.size != original_size:
        copy = copy.filter(
            ImageFilter.UnsharpMask(
                radius=SHARPEN_RADIUS,
                percent=SHARPEN_PERCENT,
                threshold=SHARPEN_THRESHOLD,
            )
        )

    return copy


def convert_to_rgb(image: Image.Image) -> Image.Image:
    if image.mode == "RGB":
        return image

    if image.mode in ("RGBA", "LA"):
        background = Image.new("RGB", image.size, BACKGROUND)
        alpha = image.getchannel("A")
        background.paste(image.convert("RGB"), mask=alpha)
        return background

    return image.convert("RGB")


def srgb_profile_bytes() -> bytes | None:
    try:
        profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB"))
        return profile.tobytes()
    except Exception:
        return None


def convert_embedded_profile_to_srgb(
    image: Image.Image,
    embedded_icc: bytes | None,
) -> Image.Image:
    """
    Convert an embedded source profile (Adobe RGB, Display P3, etc.) to sRGB.
    If no valid profile exists, the image is treated as already sRGB.
    """
    image = convert_to_rgb(image)

    if not COLOR_MANAGEMENT_ENABLED or not embedded_icc:
        return image

    try:
        source_profile = ImageCms.ImageCmsProfile(
            __import__("io").BytesIO(embedded_icc)
        )
        destination_profile = ImageCms.createProfile("sRGB")

        return ImageCms.profileToProfile(
            image,
            source_profile,
            destination_profile,
            outputMode="RGB",
            renderingIntent=ImageCms.Intent.PERCEPTUAL,
        )
    except Exception:
        # Broken or unsupported ICC profiles should not stop batch processing.
        return image


def save_with_pillow(
    canvas: Image.Image,
    destination: Path,
    output_icc: bytes | None,
) -> None:
    save_kwargs: dict[str, Any] = {
        "format": "JPEG",
        "quality": JPEG_QUALITY,
        "subsampling": JPEG_SUBSAMPLING,
        "optimize": True,
        "progressive": True,
    }

    if output_icc:
        save_kwargs["icc_profile"] = output_icc

    canvas.save(destination, **save_kwargs)


def save_with_mozjpeg(
    canvas: Image.Image,
    destination: Path,
    cjpeg: str,
) -> None:
    """
    Feed a temporary PPM to mozjpeg's cjpeg.
    PPM is lossless, so there is no extra JPEG generation.
    """
    temp_ppm = destination.with_suffix(".mozjpeg-temp.ppm")

    try:
        canvas.save(temp_ppm, format="PPM")

        command = [
            cjpeg,
            "-quality", str(JPEG_QUALITY),
            "-sample", "1x1",
            "-progressive",
            "-optimize",
            "-outfile", str(destination),
            str(temp_ppm),
        ]

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "mozjpeg cjpeg failed")
    finally:
        temp_ppm.unlink(missing_ok=True)


def create_passepartout(
    source: Path,
    destination: Path,
    caption: str,
) -> str:
    with Image.open(source) as raw:
        embedded_icc = raw.info.get("icc_profile")
        image = ImageOps.exif_transpose(raw)
        image = convert_embedded_profile_to_srgb(image, embedded_icc)

        orientation, layout = choose_layout(image.width, image.height)

        left_margin = int(layout["left"])
        right_margin = int(layout["right"])
        top_margin = int(layout["top"])
        bottom_margin = int(layout["bottom"])

        available_w = CANVAS_W - left_margin - right_margin
        available_h = CANVAS_H - top_margin - bottom_margin

        if available_w <= 0 or available_h <= 0:
            raise ValueError(f"Invalid {orientation} layout margins")

        fitted = fit_image(image, available_w, available_h)

        canvas = Image.new("RGB", (CANVAS_W, CANVAS_H), BACKGROUND)

        image_x = (CANVAS_W - fitted.width) // 2

        if layout["vertical_align"] == "top":
            image_y = top_margin
        else:
            image_y = top_margin + max(0, (available_h - fitted.height) // 2)

        image_y += int(layout.get("y_offset", 0))

        min_y = top_margin
        max_y = top_margin + max(0, available_h - fitted.height)
        image_y = max(min_y, min(image_y, max_y))

        canvas.paste(fitted, (image_x, image_y))

        draw = ImageDraw.Draw(canvas)
        font = find_font(FONT_SIZE)

        caption_y = image_y + fitted.height + CAPTION_TOP_GAP
        text_box = draw.textbbox((0, 0), caption, font=font)
        text_w = text_box[2] - text_box[0]
        text_x = (CANVAS_W - text_w) // 2

        max_caption_y = CANVAS_H - FONT_SIZE - 25
        caption_y = min(caption_y, max_caption_y)

        draw.text(
            (text_x, caption_y),
            caption,
            fill=TEXT_COLOR,
            font=font,
        )

        output_icc = srgb_profile_bytes() if COLOR_MANAGEMENT_ENABLED else None
        cjpeg = shutil.which("cjpeg") if USE_MOZJPEG_IF_AVAILABLE else None

        if cjpeg:
            try:
                save_with_mozjpeg(canvas, destination, cjpeg)

                # cjpeg does not embed ICC here; add only the safe sRGB profile.
                if output_icc:
                    exiftool = shutil.which("exiftool")
                    if exiftool:
                        profile_file = destination.with_suffix(".srgb.icc")
                        try:
                            profile_file.write_bytes(output_icc)
                            subprocess.run(
                                [
                                    exiftool,
                                    "-overwrite_original",
                                    f"-ICC_Profile<={profile_file}",
                                    str(destination),
                                ],
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                                check=False,
                            )
                        finally:
                            profile_file.unlink(missing_ok=True)
                return orientation
            except Exception:
                # Fall back to Pillow if mozjpeg is present but fails.
                destination.unlink(missing_ok=True)

        save_with_pillow(canvas, destination, output_icc)
        return orientation


def llm_preview(source: Path) -> bytes:
    """A downscaled sRGB JPEG of the photo — what the model actually looks at."""
    with Image.open(source) as raw:
        image = ImageOps.exif_transpose(raw)
        image = convert_to_rgb(image)
        image.thumbnail(
            (LLM_PREVIEW_MAX_SIDE, LLM_PREVIEW_MAX_SIDE),
            Image.Resampling.LANCZOS,
        )

        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=LLM_PREVIEW_QUALITY)
        return buffer.getvalue()


def normalize_tags(raw_tags: Any) -> list[str]:
    """'#Street Photo' -> 'streetphoto'. Drops junk, keeps order, removes duplicates."""
    if not isinstance(raw_tags, list):
        return []

    tags: list[str] = []

    for item in raw_tags:
        if not isinstance(item, str):
            continue

        tag = item.strip().lstrip("#").replace(" ", "").lower()
        tag = "".join(char for char in tag if char.isalnum() or char == "_")

        if tag and tag not in tags:
            tags.append(tag)

    return tags


class Config:
    """config.json, already validated. A missing or broken file falls back to the defaults."""

    def __init__(self, data: dict[str, Any] | None = None) -> None:
        data = data or {}

        language = data.get("description_language")
        self.language: str = language.strip() if isinstance(language, str) and language.strip() else DEFAULT_LANGUAGE

        prompt = data.get("prompt")
        if isinstance(prompt, list) and prompt:
            self.prompt_lines: list[str] = [str(line) for line in prompt]
        elif isinstance(prompt, str) and prompt.strip():
            self.prompt_lines = prompt.splitlines()
        else:
            self.prompt_lines = list(DEFAULT_PROMPT)

        hashtags = data.get("hashtags")
        hashtags = hashtags if isinstance(hashtags, dict) else {}

        self.always: list[str] = normalize_tags(hashtags.get("always"))

        self.genres: dict[str, list[str]] = {}
        raw_genres = hashtags.get("genres")

        if isinstance(raw_genres, dict):
            for name, tags in raw_genres.items():
                self.genres[str(name).strip().lower()] = normalize_tags(tags)


def load_config() -> Config:
    path = project_root() / CONFIG_FILE_NAME

    if not path.exists():
        print(f"WARNING: {CONFIG_FILE_NAME} not found - using the built-in prompt and no mandatory tags.")
        return Config()

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"WARNING: {CONFIG_FILE_NAME} could not be read ({exc}) - using the built-in prompt.")
        return Config()

    return Config(data)


def build_prompt(config: Config) -> str:
    genre_list = ", ".join(sorted(config.genres))

    lines = []

    for line in config.prompt_lines:
        # A line that asks for a genre is pointless when config.json defines none.
        if "{genres}" in line and not config.genres:
            continue

        try:
            lines.append(
                line.format(
                    language=config.language,
                    min=HASHTAGS_MIN,
                    max=HASHTAGS_MAX,
                    genres=genre_list,
                )
            )
        except (KeyError, IndexError):
            # An unknown {placeholder} in the prompt is passed through as written.
            lines.append(line)

    return "\n".join(lines)


def build_schema(genres: dict[str, list[str]]) -> dict[str, Any]:
    schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "description": {"type": "string"},
            "hashtags": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["description", "hashtags"],
    }

    if genres:
        schema["properties"]["genre"] = {"type": "string", "enum": sorted(genres)}
        schema["required"].append("genre")

    return schema


def ask_llm(preview: bytes, config: Config) -> dict[str, Any]:
    payload = {
        "model": OLLAMA_MODEL,
        "stream": False,
        "format": build_schema(config.genres),
        "options": {"temperature": LLM_TEMPERATURE},
        "messages": [
            {
                "role": "user",
                "content": build_prompt(config),
                "images": [base64.b64encode(preview).decode("ascii")],
            }
        ],
    }

    request = urllib.request.Request(
        f"{OLLAMA_URL.rstrip('/')}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=LLM_TIMEOUT_SECONDS) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"Ollama returned {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"Ollama is not reachable at {OLLAMA_URL} ({exc.reason}). "
            "Start it with: docker compose up -d"
        ) from exc

    content = body.get("message", {}).get("content", "")
    if not content:
        raise RuntimeError("Ollama returned an empty answer")

    return json.loads(content)


def merge_hashtags(llm_tags: list[str], genre: str, config: Config) -> list[str]:
    """Mandatory tags come first and are never dropped; the model's own tags fill the rest."""
    mandatory = config.genres.get(genre, []) + config.always

    merged = normalize_tags(mandatory)
    room_left = max(0, HASHTAGS_TOTAL_MAX - len(merged))

    for tag in llm_tags[:HASHTAGS_MAX]:
        if room_left == 0:
            break
        if tag not in merged:
            merged.append(tag)
            room_left -= 1

    return merged


def format_hashtags(tags: list[str]) -> str:
    lines = [
        " ".join(f"#{tag}" for tag in tags[start:start + HASHTAGS_PER_LINE])
        for start in range(0, len(tags), HASHTAGS_PER_LINE)
    ]
    return "\n".join(lines)


def build_sidecar_text(description: str, tags: list[str], caption: str) -> str:
    blocks = []

    if description:
        # Models answer in lower case often enough to be worth fixing here.
        blocks.append(description[0].upper() + description[1:])

    if caption.strip():
        blocks.append(caption.strip())

    if tags:
        blocks.append(format_hashtags(tags))

    return "\n\n".join(blocks) + "\n"


def write_sidecar(
    source: Path,
    destination: Path,
    caption: str,
    config: Config,
) -> tuple[Path, str, str]:
    """
    Writes <name>_passepartout.txt and returns its path, the detected genre and a
    warning string. The warning is empty on success; when the LLM is unavailable
    the sidecar still gets the metadata line and the mandatory 'always' tags.
    """
    sidecar = destination.with_suffix(SIDECAR_EXTENSION)

    description = ""
    genre = ""
    llm_tags: list[str] = []
    warning = ""

    if SIDECAR_ENABLED:
        try:
            answer = ask_llm(llm_preview(source), config)

            raw_description = answer.get("description", "")
            if isinstance(raw_description, str):
                description = raw_description.strip().strip('"')

            raw_genre = answer.get("genre", "")
            if isinstance(raw_genre, str):
                genre = raw_genre.strip().lower()

            llm_tags = normalize_tags(answer.get("hashtags"))
        except Exception as exc:
            warning = str(exc)

    tags = merge_hashtags(llm_tags, genre, config)

    sidecar.write_text(build_sidecar_text(description, tags, caption), encoding="utf-8")
    return sidecar, genre, warning


def move_original(source: Path, originals_dir: Path) -> Path:
    destination = unique_path(originals_dir / source.name)
    shutil.move(str(source), str(destination))
    return destination


def log_error(log_path: Path, source: Path, exc: Exception) -> None:
    with log_path.open("a", encoding="utf-8") as log:
        log.write(f"{source.name}: {type(exc).__name__}: {exc}\n")


def main() -> int:
    root = project_root()
    input_dir = root / INPUT_DIR_NAME
    processed_dir = root / PROCESSED_DIR_NAME
    originals_dir = root / ORIGINALS_DIR_NAME
    error_log = root / ERROR_LOG_NAME

    input_dir.mkdir(exist_ok=True)
    processed_dir.mkdir(exist_ok=True)
    originals_dir.mkdir(exist_ok=True)

    try:
        exiftool = find_exiftool()
    except RuntimeError as exc:
        print(f"ERROR: {exc}")
        return 1

    files = sorted(
        path for path in input_dir.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    )

    if not files:
        print(f"No supported images found in {INPUT_DIR_NAME}/")
        print("Supported:", ", ".join(sorted(SUPPORTED_EXTENSIONS)))
        return 0

    config = load_config()

    ok = 0
    failed = 0

    for source in files:
        print(f"Processing: {source.name}")

        output_name = f"{source.stem}_passepartout.jpg"
        destination = unique_path(processed_dir / output_name)

        try:
            metadata = read_metadata(exiftool, source)
            caption = build_caption(metadata)
            orientation = create_passepartout(source, destination, caption)
            sidecar, genre, warning = write_sidecar(source, destination, caption, config)
            moved_to = move_original(source, originals_dir)

            print(f"  Layout: {orientation}")
            print(f"  Saved: {destination.name}")
            print(f"  Caption: {caption.strip() or '(no EXIF data)'}")
            print(f"  Sidecar: {sidecar.name}{f' (genre: {genre})' if genre else ''}")

            if warning:
                print(f"  WARNING: no description or hashtags - {warning}")
                log_error(error_log, source, RuntimeError(warning))

            print(f"  Original: {moved_to.name}")
            ok += 1

        except Exception as exc:
            print(f"  ERROR: {exc}")
            log_error(error_log, source, exc)
            failed += 1

    print()
    print(f"Done. Successful: {ok}; Failed: {failed}")
    if failed:
        print(f"See: {error_log.name}")

    return 0 if failed == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
