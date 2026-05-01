@echo off
echo ============================================
echo   HireFlow AI - Starting Application
echo ============================================
echo.

REM ── Start Backend ────────────────────────────
echo Starting backend (Flask) on http://localhost:5001 ...
cd backend
start "HireFlow Backend" cmd /k "call venv\Scripts\activate.bat && python app.py"
cd ..

REM Wait a moment for Flask to boot
timeout /t 3 /nobreak >nul

REM ── Start Frontend ───────────────────────────
echo Starting frontend (Vite) on http://localhost:5173 ...
cd frontend
start "HireFlow Frontend" cmd /k "npm run dev"
cd ..

REM Wait for Vite to start
timeout /t 4 /nobreak >nul

REM ── Open browser ─────────────────────────────
echo Opening HireFlow AI in your browser...
start http://localhost:5173

echo.
echo ============================================
echo   App is running!
echo   Frontend : http://localhost:5173
echo   Backend  : http://localhost:5001
echo
echo   Close the two terminal windows to stop.
echo ============================================
