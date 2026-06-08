@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] .venv\Scripts\python.exe not found.
    echo Create the virtual environment first, for example:
    echo D:\Anaconda\python.exe -m venv .venv
    pause
    exit /b 1
)

if "%~1"=="--check" (
    echo [OK] install_deps.bat check passed.
    exit /b 0
)

echo [INFO] Installing project dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements.txt

if errorlevel 1 (
    echo [ERROR] Dependency installation failed. Check network, mirror, or proxy settings.
    pause
    exit /b 1
)

echo [OK] Dependencies installed.
pause
