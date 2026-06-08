@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] .venv\Scripts\python.exe not found.
    echo Create the virtual environment first, then run install_deps.bat.
    pause
    exit /b 1
)

if "%~1"=="--check" (
    echo [OK] start_fastapi.bat check passed.
    exit /b 0
)

echo [INFO] Starting FastAPI...
echo [URL] http://127.0.0.1:8000/docs
".venv\Scripts\python.exe" -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

pause
