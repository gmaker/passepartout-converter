#!/usr/bin/env python3
"""
Instagram passe-partout processor.

Workflow:
1. Reads supported images from the folder where this script is located.
2. Reads camera metadata with ExifTool.
3. Creates a 1080x1350 white canvas.
4. Fits the image without cropping.
5. Adds a centered metadata caption below the image.
6. Saves the result to ./processed
7. Moves the original to ./originals only after a successful export.

HEIC/HEIF:
Use heic2jpeg.bat first, unless Pillow on your system has HEIC support.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
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

PROCESSED_DIR_NAME = "processed"
ORIGINALS_DIR_NAME = "originals"
ERROR_LOG_NAME = "process-errors.log"

# =========================


def script_dir() -> Path:
    return Path(__file__).resolve().parent


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


def move_original(source: Path, originals_dir: Path) -> Path:
    destination = unique_path(originals_dir / source.name)
    shutil.move(str(source), str(destination))
    return destination


def log_error(log_path: Path, source: Path, exc: Exception) -> None:
    with log_path.open("a", encoding="utf-8") as log:
        log.write(f"{source.name}: {type(exc).__name__}: {exc}\n")


def main() -> int:
    root = script_dir()
    processed_dir = root / PROCESSED_DIR_NAME
    originals_dir = root / ORIGINALS_DIR_NAME
    error_log = root / ERROR_LOG_NAME

    processed_dir.mkdir(exist_ok=True)
    originals_dir.mkdir(exist_ok=True)

    try:
        exiftool = find_exiftool()
    except RuntimeError as exc:
        print(f"ERROR: {exc}")
        return 1

    files = sorted(
        path for path in root.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    )

    if not files:
        print("No supported images found in the script folder.")
        print("Supported:", ", ".join(sorted(SUPPORTED_EXTENSIONS)))
        return 0

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
            moved_to = move_original(source, originals_dir)

            print(f"  Layout: {orientation}")
            print(f"  Saved: {destination.name}")
            print(f"  Caption: {caption.strip() or '(no EXIF data)'}")
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
