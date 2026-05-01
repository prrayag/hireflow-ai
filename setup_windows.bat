@echo off
echo ============================================
echo   HireFlow AI - Windows Setup Script
echo ============================================
echo.

REM ── Check Python ────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.10+ from https://python.org
    echo Make sure to check "Add Python to PATH" during install.
    pause
    exit /b 1
)
echo [OK] Python found.

REM ── Check Node.js ───────────────────────────
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js is not installed or not in PATH.
    echo Please install Node.js from https://nodejs.org (LTS version)
    pause
    exit /b 1
)
echo [OK] Node.js found.

REM ── Backend setup ───────────────────────────
echo.
echo [1/4] Setting up Python virtual environment...
cd backend
python -m venv venv
call venv\Scripts\activate.bat

echo [2/4] Installing Python dependencies...
pip install -r requirements.txt

REM Install easyocr (optional - needed for scanned PDFs)
pip install easyocr

cd ..

REM ── Frontend setup ──────────────────────────
echo.
echo [3/4] Installing frontend dependencies...
cd frontend
npm install
cd ..

echo.
echo [4/4] Setup complete!
echo.
echo ============================================
echo   To START the app, run:  start_windows.bat
echo ============================================
echo.
pause
