@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

rem First run: installs everything the pipeline needs via winget.
rem Already-installed tools are left alone.

if /i "%~1"=="--no-pause" set "NOPAUSE=1"

where winget >nul 2>nul
if errorlevel 1 (
    echo winget was not found.
    echo It ships with "App Installer" from the Microsoft Store on Windows 10 and 11.
    echo Install the tools by hand instead:
    echo   Python    https://www.python.org/downloads/
    echo   ExifTool  https://exiftool.org/
    echo   FFmpeg    https://www.gyan.dev/ffmpeg/builds/
    echo   Docker    https://www.docker.com/products/docker-desktop/
    if not defined NOPAUSE pause
    exit /b 1
)

echo FFmpeg is only needed for HEIC photos, Docker only for the descriptions.
echo.

rem Parentheses in the third argument would break the if-blocks in :INSTALL.
call :INSTALL python   "Python.Python.3.12"    "Python"
call :INSTALL exiftool "OliverBetz.ExifTool"   "ExifTool"
call :INSTALL ffmpeg   "Gyan.FFmpeg"           "FFmpeg"
call :INSTALL docker   "Docker.DockerDesktop"  "Docker Desktop"

echo.
echo Installing Pillow...
python -m pip install --upgrade Pillow
if errorlevel 1 echo WARNING: Pillow could not be installed. Open a new terminal and retry - a fresh Python needs one.

echo.
echo Done. Close this window, open a new one so PATH is picked up,
echo then put your photos into input\ and run bin\run-all.bat
if not defined NOPAUSE pause
exit /b

:INSTALL
rem %1 = command to look for, %2 = winget id, %3 = human name
where %~1 >nul 2>nul
if not errorlevel 1 (
    echo [ok] %~3 is already installed.
    exit /b
)

echo.
echo Installing %~3 ...
winget install --exact --id %~2 --accept-package-agreements --accept-source-agreements --silent
if errorlevel 1 echo WARNING: %~3 could not be installed automatically.
exit /b
