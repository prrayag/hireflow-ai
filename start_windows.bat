@echo off
setlocal
set "ROOT=%~dp0"
cd /d "%ROOT%"

echo ============================================
echo   HireFlow AI - Starting Application
echo ============================================
echo.

if not exist "%ROOT%backend\venv\Scripts\python.exe" (
    echo [ERROR] Backend not set up. Run setup_windows.bat first.
    pause
    exit /b 1
)
if not exist "%ROOT%frontend\node_modules\.bin\vite.cmd" (
    echo [ERROR] Frontend not set up. Run setup_windows.bat first.
    pause
    exit /b 1
)

REM ── Start Backend (use venv python directly - avoids activate.bat issues) ──
echo Starting backend (Flask) on http://localhost:5001 ...
start "HireFlow Backend" cmd /k "cd /d "%ROOT%backend" && venv\Scripts\python.exe app.py"

timeout /t 5 /nobreak >nul

REM ── Start Frontend ───────────────────────────
echo Starting frontend (Vite) on http://localhost:5173 ...
start "HireFlow Frontend" cmd /k "cd /d "%ROOT%frontend" && npm run dev"

timeout /t 6 /nobreak >nul

echo Opening HireFlow AI in your browser...
start http://localhost:5173

echo.
echo ============================================
echo   App is starting!
echo   Frontend : http://localhost:5173
echo   Backend  : http://localhost:5001
echo   Spark UI : http://localhost:4040
echo.
echo   If the page does not load, wait 10 seconds and refresh.
echo   Close the two terminal windows to stop.
echo ============================================
pause
