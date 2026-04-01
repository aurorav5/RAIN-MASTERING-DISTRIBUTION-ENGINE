@echo off
REM ============================================
REM RAIN AI Mastering Engine v6.0 - Local Runner
REM ============================================
REM Serves the pre-built RAIN frontend locally.
REM Double-click this file to start RAIN.
REM Opens in your browser at http://localhost:4173
REM
REM NOTE: This starts the FRONTEND ONLY. The local-first
REM mastering engine runs entirely in your browser via WASM.
REM No backend server is needed for local mastering.
REM
REM Requirements: Node.js 18+ installed
REM ============================================

echo.
echo   ========================================
echo     R-N AI MASTERING ENGINE v6.0
echo     ARCOVEL Technologies International
echo.
echo     Rain doesn't live in the cloud.
echo   ========================================
echo.

cd /d "%~dp0frontend"

if not exist "dist\index.html" (
    echo ERROR: Build not found. Run: npm install ^&^& npx vite build
    pause
    exit /b 1
)

echo   Starting RAIN...
echo   Open: http://localhost:4173
echo.

npx vite preview --host 0.0.0.0 --port 4173

pause
