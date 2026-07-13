@echo off
setlocal

rem docker-compose.yml sits in the project root, one level above src\.
cd /d "%~dp0.."

where docker >nul 2>nul
if errorlevel 1 (
    echo Docker was not found in PATH. Install Docker Desktop.
    pause
    exit /b 1
)

echo Starting Ollama and downloading the vision model if needed.
echo The first run pulls several gigabytes and can take a while.
echo.

docker compose up -d
if errorlevel 1 (
    echo Failed to start the Ollama container.
    pause
    exit /b 1
)

rem model-init exits once the model is in the shared volume.
docker compose logs -f model-init

echo.
echo Ollama is running at http://localhost:11434
echo You can now run run-passepartout.bat
pause
