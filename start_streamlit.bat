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
    echo [OK] start_streamlit.bat check passed.
    exit /b 0
)

echo [INFO] Starting Streamlit...
echo [URL] http://localhost:8501
".venv\Scripts\python.exe" -m streamlit run streamlit_app.py

pause
