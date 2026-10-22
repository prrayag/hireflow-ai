@echo off
setlocal EnableDelayedExpansion
set "ROOT=%~dp0"
cd /d "%ROOT%"

echo ============================================
echo   HireFlow AI - Windows Setup Script
echo ============================================
echo.
echo Project folder: %ROOT%
echo.

REM ── Check Python ────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Install Python 3.10+ from https://python.org
    echo Tick "Add Python to PATH" during install.
    pause
    exit /b 1
)
echo [OK] Python found.

REM ── Check Node.js ───────────────────────────
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js is not installed or not in PATH.
    echo Install Node.js LTS from https://nodejs.org
    pause
    exit /b 1
)
echo [OK] Node.js found.

REM ── Check Java (PySpark 4 needs Java 17+) ───
java -version >nul 2>&1
if errorlevel 1 (
    echo [WARN] Java not found. Backend will fail until you install JDK 17.
    echo Download: https://adoptium.net/temurin/releases/?version=17
) else (
    echo [OK] Java found.
)

REM ── Backend setup ───────────────────────────
echo.
echo [1/4] Creating Python virtual environment...
cd /d "%ROOT%backend"
if not exist "venv\Scripts\python.exe" (
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create venv.
        pause
        exit /b 1
    )
)
echo [OK] venv ready.

echo [2/4] Installing Python dependencies (may take 10-20 min)...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install --no-cache-dir -r requirements.txt
if errorlevel 1 (
    echo [ERROR] pip install failed. Try running CMD as Administrator, then run this script again.
    pause
    exit /b 1
)
pip install --no-cache-dir easyocr
cd /d "%ROOT%"

REM ── Frontend setup ──────────────────────────
echo.
echo [3/4] Installing frontend dependencies...
cd /d "%ROOT%frontend"
call npm install
if errorlevel 1 (
    echo [ERROR] npm install failed.
    pause
    exit /b 1
)
cd /d "%ROOT%"

echo.
echo [4/4] Verifying install...
set "OK=1"
if not exist "%ROOT%backend\venv\Scripts\python.exe" set "OK=0"
if not exist "%ROOT%frontend\node_modules\.bin\vite.cmd" set "OK=0"

if "%OK%"=="0" (
    echo [ERROR] Setup incomplete. Check errors above.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Setup complete!
echo   To START the app, run:  start_windows.bat
echo ============================================
echo.
pause
