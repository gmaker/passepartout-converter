@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo Python was not found in PATH.
    echo Install Python and enable "Add Python to PATH".
    pause
    exit /b 1
)

python -c "import PIL" >nul 2>nul
if errorlevel 1 (
    echo Installing Pillow...
    python -m pip install --upgrade Pillow
    if errorlevel 1 (
        echo Failed to install Pillow.
        pause
        exit /b 1
    )
)

python "%~dp0passepartout_processor.py"
echo.
pause
