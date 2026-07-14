@echo off
setlocal EnableExtensions EnableDelayedExpansion

rem The whole pipeline: start the LLM, convert HEIC, build the passe-partouts.
rem Put your photos into the input folder in the project root, then run this.
cd /d "%~dp0.."

if /i "%~1"=="--no-pause" set "NOPAUSE=1"

if not exist "%CD%\input" mkdir "%CD%\input"

set "SKIP_LLM="

where docker >nul 2>nul
if errorlevel 1 (
    echo Docker was not found in PATH - continuing without descriptions and hashtags.
    set "SKIP_LLM=1"
)

if not defined SKIP_LLM (
    echo [1/3] Starting the local LLM. The first run downloads about 6 GB.

    docker compose up -d ollama
    if errorlevel 1 (
        echo Ollama could not be started - continuing without descriptions and hashtags.
        echo Is Docker Desktop running?
        set "SKIP_LLM=1"
    )
)

if not defined SKIP_LLM (
    rem Pulls the model if the volume is empty, exits immediately otherwise.
    docker compose up model-init
    if errorlevel 1 (
        echo The model could not be downloaded - continuing without descriptions and hashtags.
        set "SKIP_LLM=1"
    )
)

if defined SKIP_LLM (
    echo.
    echo The .txt files will hold the camera metadata only.
    echo.
)

echo.
echo [2/3] Converting HEIC files, if there are any.

set "HAS_HEIC="
for %%F in (input\*.heic input\*.heif) do set "HAS_HEIC=1"

if defined HAS_HEIC (
    call "%~dp0heic2jpeg-with-metadata.bat" --no-pause
) else (
    echo No HEIC files found - skipping.
)

echo.
echo [3/3] Building the passe-partouts.
call "%~dp0run-passepartout.bat" --no-pause

echo.
echo All done. Look into "processed".
if not defined NOPAUSE pause
