@echo off
setlocal EnableExtensions EnableDelayedExpansion

rem This script lives in src\ — everything it touches sits in the project root.
cd /d "%~dp0.."

rem run-all.bat calls this with --no-pause so the window is not held twice.
if /i "%~1"=="--no-pause" set "NOPAUSE=1"

set "INPUT=%CD%\input"
set "ORIGINALS=%CD%\originals"
set "LOG=%CD%\heic2jpeg-errors.log"

if not exist "%INPUT%" mkdir "%INPUT%"
if not exist "%ORIGINALS%" mkdir "%ORIGINALS%"

cd /d "%INPUT%"

where ffmpeg >nul 2>nul
if errorlevel 1 (
    echo ERROR: ffmpeg was not found in PATH.
    if not defined NOPAUSE pause
    exit /b 1
)

where exiftool >nul 2>nul
if errorlevel 1 (
    echo ERROR: exiftool was not found in PATH.
    if not defined NOPAUSE pause
    exit /b 1
)

set /a OK=0
set /a FAIL=0

for %%F in (*.heic *.HEIC *.heif *.HEIF) do (
    if exist "%%~fF" call :PROCESS "%%~fF"
)

echo.
echo Done. Successful: %OK%  Failed: %FAIL%
if not "%FAIL%"=="0" echo See: "%LOG%"
if not defined NOPAUSE pause
exit /b

:PROCESS
set "INPUT=%~1"
set "BASE=%~n1"
set "OUTPUT=%~dp1%BASE%.jpg"

if exist "%OUTPUT%" (
    echo SKIP: "%~nx1" - JPEG already exists.
    exit /b
)

echo Converting: "%~nx1"

ffmpeg -hide_banner -loglevel error -y -i "%INPUT%" -frames:v 1 -q:v 1 "%OUTPUT%"
if errorlevel 1 (
    echo FAILED: "%~nx1"
    >>"%LOG%" echo FFmpeg failed: "%INPUT%"
    if exist "%OUTPUT%" del /q "%OUTPUT%"
    set /a FAIL+=1
    exit /b
)

rem Copy photographic metadata, ICC profile and timestamps.
rem Do not copy Orientation because FFmpeg already rendered the pixels.
exiftool -overwrite_original ^
  -TagsFromFile "%INPUT%" ^
  -EXIF:All -XMP:All -IPTC:All -ICC_Profile ^
  -Orientation= ^
  "%OUTPUT%" >nul 2>>"%LOG%"

if errorlevel 1 (
    echo WARNING: JPEG created, but metadata copy failed.
    >>"%LOG%" echo ExifTool metadata copy failed: "%INPUT%" to "%OUTPUT%"
)

call :UNIQUE_ORIGINAL "%ORIGINALS%\%~nx1"
set "DEST=!UNIQUE_DEST!"

move /y "%INPUT%" "!DEST!" >nul
if errorlevel 1 (
    echo WARNING: JPEG created, but original could not be moved.
    >>"%LOG%" echo Move failed: "%INPUT%" to "!DEST!"
    set /a FAIL+=1
    exit /b
)

echo OK: "%~nx1" to "%~n1.jpg"
set /a OK+=1
exit /b

:UNIQUE_ORIGINAL
set "UNIQUE_DEST=%~1"
if not exist "!UNIQUE_DEST!" exit /b

set "U_DIR=%~dp1"
set "U_NAME=%~n1"
set "U_EXT=%~x1"
set /a U_NUM=1

:UNIQUE_LOOP
set "UNIQUE_DEST=!U_DIR!!U_NAME!_!U_NUM!!U_EXT!"
if exist "!UNIQUE_DEST!" (
    set /a U_NUM+=1
    goto UNIQUE_LOOP
)
exit /b
