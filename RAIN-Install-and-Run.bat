@echo off
setlocal enabledelayedexpansion
title R∞N AI Mastering Engine v6.0 — Installer
color 0A

echo.
echo  ================================================================
echo   R8N AI MASTERING ENGINE v6.0
echo   ARCOVEL Technologies International
echo.
echo   One-click installer and launcher
echo   Rain doesn't live in the cloud.
echo  ================================================================
echo.

:: ---------------------------------------------------------------
:: Step 1: Check Node.js
:: ---------------------------------------------------------------
echo  [1/5] Checking Node.js...
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  ERROR: Node.js is not installed.
    echo.
    echo  Please install Node.js 18+ from:
    echo    https://nodejs.org/en/download
    echo.
    echo  After installing, run this file again.
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('node --version') do set NODE_VER=%%v
echo  Found Node.js %NODE_VER%

:: ---------------------------------------------------------------
:: Step 2: Check if we're in the right directory
:: ---------------------------------------------------------------
echo  [2/5] Checking project files...
if not exist "frontend\package.json" (
    echo.
    echo  ERROR: Cannot find frontend\package.json
    echo  Make sure this file is in the rain-blueprint root directory.
    echo.
    pause
    exit /b 1
)
echo  Project files found.

:: ---------------------------------------------------------------
:: Step 3: Install dependencies (skip if node_modules exists)
:: ---------------------------------------------------------------
echo  [3/5] Installing dependencies...
if exist "frontend\node_modules\.package-lock.json" (
    echo  Dependencies already installed. Skipping.
) else (
    cd frontend
    call npm install --no-audit --no-fund
    if %errorlevel% neq 0 (
        echo  ERROR: npm install failed.
        pause
        exit /b 1
    )
    cd ..
    echo  Dependencies installed.
)

:: ---------------------------------------------------------------
:: Step 4: Build production frontend (skip if dist exists)
:: ---------------------------------------------------------------
echo  [4/5] Building production frontend...
if exist "frontend\dist\index.html" (
    echo  Production build already exists. Skipping.
    echo  (Delete frontend\dist to force rebuild)
) else (
    cd frontend
    call npx vite build
    if %errorlevel% neq 0 (
        echo  ERROR: Build failed.
        pause
        exit /b 1
    )
    cd ..
    echo  Build complete.
)

:: ---------------------------------------------------------------
:: Step 5: Launch
:: ---------------------------------------------------------------
echo  [5/5] Starting R∞N...
echo.
echo  ================================================================
echo.
echo   R∞N is starting at:
echo.
echo     http://localhost:4173
echo.
echo   Opening in your default browser...
echo.
echo   Press Ctrl+C to stop the server.
echo.
echo  ================================================================
echo.

:: Open browser after 2 second delay
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:4173"

:: Start the preview server (blocks until Ctrl+C)
cd frontend
call npx vite preview --host 0.0.0.0 --port 4173

pause
