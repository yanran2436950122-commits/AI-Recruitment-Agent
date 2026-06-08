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
    echo [OK] start_all.bat check passed.
    exit /b 0
)

set "PYTHON=%CD%\.venv\Scripts\python.exe"

echo [INFO] Opening FastAPI and Streamlit in separate windows...
echo [FastAPI] http://127.0.0.1:8000/docs
echo [Streamlit] http://localhost:8501

start "AI Recruitment FastAPI" cmd /k ""%PYTHON%" -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
start "AI Recruitment Streamlit" cmd /k ""%PYTHON%" -m streamlit run streamlit_app.py"

echo [OK] Startup commands were sent. Check the two new command windows.
pause
