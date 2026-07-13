# passepartout-converter

Turns raw camera photos into Instagram-ready 1080×1350 images: the photo is placed, uncropped, on a white passe-partout canvas, with a centered caption underneath showing the shooting parameters read from EXIF (focal length, aperture, shutter speed, ISO).

```
77mm   ·   f/2.8   ·   1/111s   ·   ISO 32
```

## Example

A 3:4 iPhone shot goes in, a 1080×1350 passe-partout comes out. Nothing is cropped — the photo is scaled to fit inside the margins, and the shooting parameters are printed underneath.

| Source | Result |
| --- | --- |
| <img src="examples/source.jpg" width="380"> | <img src="examples/result.jpg" width="380"> |

Both files are in [`examples/`](examples).

## What it does

`passepartout_processor.py` scans the folder it lives in for supported images and, for each one:

1. Reads camera metadata with ExifTool.
2. Applies EXIF orientation, then converts any embedded ICC profile (Adobe RGB, Display P3, …) to sRGB.
3. Picks a layout automatically — portrait, landscape or square — so landscape shots get narrower side margins and stay large on a phone screen.
4. Fits the photo into a 1080×1350 white canvas without cropping, with gentle unsharp masking after downscaling.
5. Draws the metadata caption centered below the photo.
6. Saves a JPEG (quality 97, 4:4:4, progressive) to `processed/`, using mozjpeg's `cjpeg` if it is on PATH and falling back to Pillow otherwise. Output EXIF/GPS is stripped; the sRGB profile is kept.
7. Moves the original to `originals/` — only after a successful export.

Supported input: `.jpg`, `.jpeg`, `.png`, `.webp`, `.tif`, `.tiff`, `.bmp`. Failures are logged to `process-errors.log` and never abort the batch.

`heic2jpeg-with-metadata.bat` is a pre-step for iPhone photos: it converts every `.heic`/`.heif` in the folder to JPEG with FFmpeg, copies EXIF/XMP/IPTC/ICC across with ExifTool, and moves the originals into `originals/`.

## Requirements

- **Python 3.9+** with **Pillow** — `run-passepartout.bat` installs Pillow automatically if it is missing.
- **ExifTool** on PATH — required.
- **FFmpeg** on PATH — only for the HEIC batch file.
- **mozjpeg** (`cjpeg`) on PATH — optional; slightly better compression when present.

## Usage

1. Copy the three files from this repo into a working folder.
2. Drop your photos into that same folder.
3. For iPhone `.heic` files, run `heic2jpeg-with-metadata.bat` first.
4. Run `run-passepartout.bat` (or `python passepartout_processor.py`).

Results land in `processed/`, originals in `originals/`.

## Tuning

All settings live in the block at the top of `passepartout_processor.py`: canvas size, per-orientation margins and vertical offsets, background and text color, font size, JPEG quality, sharpening, color management. The caption font falls back through Times New Roman → Arial → Calibri → DejaVu.

---

# passepartout-converter (по-русски)

Утилита готовит фотографии к публикации в Instagram: снимок без обрезки кладётся на белое паспарту 1080×1350, а под ним по центру подписываются параметры съёмки, вытащенные из EXIF — фокусное расстояние, диафрагма, выдержка, ISO.

```
77mm   ·   f/2.8   ·   1/111s   ·   ISO 32
```

## Пример

На входе кадр с айфона 3:4, на выходе паспарту 1080×1350. Ничего не обрезается: фотография масштабируется так, чтобы целиком поместиться в поля, а снизу подписываются параметры съёмки.

| Исходник | Результат |
| --- | --- |
| <img src="examples/source.jpg" width="380"> | <img src="examples/result.jpg" width="380"> |

Оба файла лежат в папке [`examples/`](examples).

## Как это работает

`passepartout_processor.py` обрабатывает все подходящие изображения из той папки, где лежит сам скрипт. Для каждого файла:

1. Читает метаданные камеры через ExifTool.
2. Применяет EXIF-ориентацию и переводит встроенный ICC-профиль (Adobe RGB, Display P3 и т.д.) в sRGB.
3. Сам выбирает раскладку — вертикальная, горизонтальная или квадрат. У горизонтальных кадров боковые поля уже, чтобы снимок оставался крупным на экране телефона.
4. Вписывает фото в белый холст 1080×1350 без кадрирования и аккуратно подшарпливает после уменьшения.
5. Рисует подпись с метаданными по центру под фотографией.
6. Сохраняет JPEG (качество 97, 4:4:4, progressive) в папку `processed/`. Если в PATH есть mozjpeg (`cjpeg`) — жмёт им, иначе Pillow. EXIF и GPS из результата вычищаются, профиль sRGB остаётся.
7. Переносит оригинал в `originals/` — только после успешного сохранения.

Поддерживаются `.jpg`, `.jpeg`, `.png`, `.webp`, `.tif`, `.tiff`, `.bmp`. Ошибки по отдельным файлам пишутся в `process-errors.log` и не останавливают пакетную обработку.

`heic2jpeg-with-metadata.bat` — подготовительный шаг для фотографий с айфона: конвертирует все `.heic`/`.heif` из папки в JPEG через FFmpeg, переносит EXIF/XMP/IPTC/ICC с помощью ExifTool и убирает оригиналы в `originals/`.

## Что нужно установить

- **Python 3.9+** и **Pillow** — `run-passepartout.bat` доставит Pillow сам, если его нет.
- **ExifTool** в PATH — обязательно.
- **FFmpeg** в PATH — только для батника с HEIC.
- **mozjpeg** (`cjpeg`) в PATH — по желанию, даёт чуть лучшее сжатие.

## Как запустить

1. Скопируйте три файла из репозитория в рабочую папку.
2. Положите туда же фотографии.
3. Если снимки в `.heic` с айфона — сначала запустите `heic2jpeg-with-metadata.bat`.
4. Запустите `run-passepartout.bat` (или `python passepartout_processor.py`).

Готовые картинки окажутся в `processed/`, исходники — в `originals/`.

## Настройка

Все параметры собраны в блоке настроек в начале `passepartout_processor.py`: размер холста, поля и вертикальные сдвиги для каждой ориентации, цвет фона и текста, размер шрифта, качество JPEG, шарпинг, управление цветом. Шрифт подписи подбирается по цепочке Times New Roman → Arial → Calibri → DejaVu.
