# passepartout-converter

Puts a photo, uncropped, on a white 1080x1350 passe-partout for Instagram and prints the shooting parameters from EXIF under it. Next to the picture it writes a `.txt` with a ready post: a description and hashtags from a local vision model. Nothing is sent anywhere, the model runs in Docker on your machine.

| Source | Result |
| --- | --- |
| <img src="examples/source.jpg" width="380"> | <img src="examples/result.jpg" width="380"> |

The `.txt` the model wrote for this photo:

```
Мирный уголок природы под тяжелым небом.

77mm   ·   f/2.8   ·   1/111s   ·   ISO 32

#landscapephotography #naturephotography #landscapelovers
#landscape #serenity #reflection
#summer #peaceful #nature
```

The first line of hashtags comes from `config.json`, the rest from the model. Set `"description_language": "English"` and the same photo comes back as *"Serene pond reflecting tranquil gazebo amidst lush greenery under cloudy sky"*. Everything is in [`examples/`](examples).

## Install

Run once. It installs Python, ExifTool, FFmpeg and Docker if they are missing, and skips whatever you already have.

```
bin\setup.bat        Windows, uses winget
bin/setup.sh         Linux and macOS, uses apt / dnf / pacman / brew
```

Then open a new terminal so the new tools land in PATH.

## Run

1. Put your photos into `input/`.
2. Run `bin\run-all.bat` on Windows or `bin/run-all.sh` on Linux and macOS.

The first run downloads the model, about 6 GB. After that a photo takes a few seconds.

```
input/       photos to process, this is where you drop them
processed/   <name>_passepartout.jpg + <name>_passepartout.txt
originals/   the source photo, moved here after a successful export
```

`input/` ends up empty: every photo either lands in `processed/` and moves to `originals/`, or stays put with the reason logged to `process-errors.log`. HEIC from an iPhone is converted automatically, keeping the metadata.

If Docker is missing or not running, `run-all` says so and carries on: you still get the passe-partout, and the `.txt` holds the metadata line without a description and hashtags.

## config.json

```json
{
  "description_language": "Russian",

  "prompt": [
    "You are writing an Instagram caption for a photographer's shot.",
    "Look at the photo and answer with JSON only.",
    "- description: one short evocative sentence in {language} ... Maximum 90 characters.",
    "- hashtags: {min} to {max} English hashtags, lowercase, no '#' sign ...",
    "- genre: the single best match for this photo from this list: {genres} ..."
  ],

  "hashtags": {
    "always": [],
    "genres": {
      "street": ["streetphotography", "streetphoto", "urbanphotography", "citylife"],
      "landscape": ["landscapephotography", "naturephotography", "landscapelovers"],
      "other": []
    }
  }
}
```

`description_language` is the language of the sentence above the hashtags, named in English: `Russian`, `English`, `German`. Hashtags stay English.

`prompt` is a list of lines. `{language}`, `{min}`, `{max}` and `{genres}` are filled in for you. Rewrite it as you like: the answer is held to a JSON schema, so the format cannot break.

`hashtags` are the tags you always want, so the result does not depend on the model's mood. `always` goes on every photo, and the model picks one genre from the keys of `genres`, whose set is added too. Adding a genre to the file is enough to make it selectable. Mandatory tags go first and are never dropped, the model's tags fill the rest up to 15. Write them without the `#`.

## Odds and ends

Other launchers in `bin/`, in both flavours: `start-llm` starts Ollama, `heic2jpeg-with-metadata` converts HEIC, `run-passepartout` builds the passe-partouts. They can be run from anywhere.

The model is `qwen2.5vl:7b`, about 6 GB, fits on a 12 GB card. A different one: `set PASSEPARTOUT_MODEL=qwen2.5vl:3b` before the run. `OLLAMA_URL` points the script at a different host. Without a GPU, delete the `deploy:` block from `docker-compose.yml` and Ollama runs on the CPU, slower but it works. `docker compose down` stops the container.

Canvas size, margins, JPEG quality, sharpening and the size of the preview sent to the model are set in the block at the top of `src/passepartout_processor.py`. If mozjpeg (`cjpeg`) is on PATH it is used for compression, otherwise Pillow.

---

# passepartout-converter (по-русски)

Кладёт фотографию без обрезки на белое паспарту 1080x1350 для инстаграма и подписывает под ней параметры съёмки из EXIF. Рядом с картинкой пишет `.txt` с готовым постом: описание и хештеги от локальной модели. Никуда ничего не уходит, модель крутится в докере на вашей машине.

Вот что модель написала для фотографии из примера выше:

```
Мирный уголок природы под тяжелым небом.

77mm   ·   f/2.8   ·   1/111s   ·   ISO 32

#landscapephotography #naturephotography #landscapelovers
#landscape #serenity #reflection
#summer #peaceful #nature
```

Первая строка хештегов пришла из `config.json`, остальные придумала модель.

## Установка

Запускается один раз. Поставит Python, ExifTool, FFmpeg и Docker, если их нет, и не тронет то, что уже стоит.

```
bin\setup.bat        Windows, через winget
bin/setup.sh         Linux и macOS, через apt / dnf / pacman / brew
```

Потом откройте новый терминал, чтобы свежие программы попали в PATH.

## Запуск

1. Положите фотографии в `input/`.
2. Запустите `bin\run-all.bat` на Windows или `bin/run-all.sh` на Linux и macOS.

При первом запуске скачается модель, около 6 ГБ. Дальше на фотографию уходит несколько секунд.

```
input/       фотографии на обработку, сюда их и кладёте
processed/   <имя>_passepartout.jpg + <имя>_passepartout.txt
originals/   исходник, уезжает сюда после успешного экспорта
```

`input/` в итоге пустеет: каждое фото либо оказывается в `processed/` и уезжает в `originals/`, либо остаётся на месте, а причина пишется в `process-errors.log`. HEIC с айфона конвертируется сам, с сохранением метаданных.

Если докера нет или он не запущен, `run-all` об этом скажет и продолжит: паспарту всё равно соберётся, а в `.txt` будет строка с метаданными, без описания и хештегов.

## config.json

```json
{
  "description_language": "Russian",

  "prompt": [
    "You are writing an Instagram caption for a photographer's shot.",
    "Look at the photo and answer with JSON only.",
    "- description: one short evocative sentence in {language} ... Maximum 90 characters.",
    "- hashtags: {min} to {max} English hashtags, lowercase, no '#' sign ...",
    "- genre: the single best match for this photo from this list: {genres} ..."
  ],

  "hashtags": {
    "always": [],
    "genres": {
      "street": ["streetphotography", "streetphoto", "urbanphotography", "citylife"],
      "landscape": ["landscapephotography", "naturephotography", "landscapelovers"],
      "other": []
    }
  }
}
```

`description_language` задаёт язык предложения над хештегами, название пишется по-английски: `Russian`, `English`, `German`. Хештеги остаются английскими.

`prompt` это список строк. `{language}`, `{min}`, `{max}` и `{genres}` подставляются сами. Переписывайте как хотите: ответ держит JSON-схема, формат не сломается.

`hashtags` это теги, которые нужны всегда, чтобы результат не зависел от настроения модели. `always` уходит на каждое фото, а жанр модель выбирает сама из ключей `genres`, и его набор тоже добавляется. Достаточно дописать жанр в файл, и он станет доступен. Обязательные теги идут первыми и никогда не выбрасываются, теги от модели дополняют список до 15 штук. Решётку писать не нужно.

## Разное

Остальные запускалки в `bin/`, в обоих вариантах: `start-llm` поднимает Ollama, `heic2jpeg-with-metadata` конвертирует HEIC, `run-passepartout` собирает паспарту. Запускать можно откуда угодно.

Модель `qwen2.5vl:7b`, около 6 ГБ, влезает в карту на 12 ГБ. Другая: `set PASSEPARTOUT_MODEL=qwen2.5vl:3b` перед запуском. `OLLAMA_URL` направит скрипт на другой хост. Без видеокарты уберите блок `deploy:` из `docker-compose.yml`, и Ollama поедет на процессоре, медленнее, но поедет. `docker compose down` гасит контейнер.

Размер холста, поля, качество JPEG, шарпинг и размер превью для модели настраиваются в блоке в начале `src/passepartout_processor.py`. Если в PATH есть mozjpeg (`cjpeg`), сжатие идёт им, иначе Pillow.
