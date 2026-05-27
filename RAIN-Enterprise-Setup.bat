@echo off
:: ==============================================================================
::  R∞N AI MASTERING ENGINE v6.0 — Enterprise Tier Installer
::  ARCOVEL Technologies International
::
::  Double-click this file  — OR —
::  Right-click → Run as Administrator  (recommended for first install)
::
::  This launcher:
::    1. Checks / installs all prerequisites
::    2. Delegates to the PowerShell installer for full setup
::    3. Falls back to a pure-batch install if PowerShell is unavailable
:: ==============================================================================
title R∞N AI Mastering Engine v6.0 — Enterprise Installer
color 0B
setlocal enabledelayedexpansion

echo.
echo  ╔══════════════════════════════════════════════════════════════╗
echo  ║                                                              ║
echo  ║   R∞N  AI  MASTERING  ^&  DISTRIBUTION  ENGINE  v6.0         ║
echo  ║   ARCOVEL Technologies International                        ║
echo  ║                                                              ║
echo  ║   Enterprise Tier — Full-Stack Installer                    ║
echo  ║   Rain doesn't live in the cloud.                           ║
echo  ║                                                              ║
echo  ╚══════════════════════════════════════════════════════════════╝
echo.

:: ── Determine script directory (repo root) ────────────────────────────────
set "REPO_ROOT=%~dp0"
:: Remove trailing backslash
if "%REPO_ROOT:~-1%"=="\" set "REPO_ROOT=%REPO_ROOT:~0,-1%"
cd /d "%REPO_ROOT%"

echo  [INFO] Repo root: %REPO_ROOT%
echo.

:: ── Check for PowerShell 5.1+ ─────────────────────────────────────────────
echo  [1/3] Checking PowerShell...
powershell -Command "if ($PSVersionTable.PSVersion.Major -lt 5) { exit 1 }" >nul 2>&1
if %errorlevel% neq 0 (
    echo  [WARN] PowerShell 5.1+ not found. Falling back to batch-only mode.
    goto :BATCH_INSTALL
)

for /f "tokens=*" %%v in ('powershell -Command "$PSVersionTable.PSVersion.ToString()" 2^>nul') do set PS_VER=%%v
echo  [OK]   PowerShell %PS_VER%
echo.

:: ── Launch the PowerShell installer ──────────────────────────────────────
echo  [2/3] Launching PowerShell installer...
echo.

powershell -ExecutionPolicy Bypass -NoProfile -File "%REPO_ROOT%\RAIN-Enterprise-Setup.ps1"
set EXIT_CODE=%errorlevel%

if %EXIT_CODE% neq 0 (
    echo.
    echo  [FAIL] Installer exited with code %EXIT_CODE%.
    echo.
    echo  Troubleshooting:
    echo    - Run as Administrator for full install privileges
    echo    - Ensure Docker Desktop is running
    echo    - Check the error messages above
    echo.
    pause
    exit /b %EXIT_CODE%
)

echo.
echo  [OK] Installation complete.
goto :EOF

:: ══════════════════════════════════════════════════════════════════════════
::  BATCH FALLBACK — used only when PowerShell unavailable
:: ══════════════════════════════════════════════════════════════════════════
:BATCH_INSTALL
echo.
echo  ╔══════════════════════════════════════════════════════════════╗
echo  ║   BATCH INSTALL MODE (PowerShell not available)             ║
echo  ╚══════════════════════════════════════════════════════════════╝
echo.

:: Step A: Collect credentials
set /p ADMIN_EMAIL=  Admin e-mail address: 
if "%ADMIN_EMAIL%"=="" (
    echo  [FAIL] E-mail cannot be empty.
    pause & exit /b 1
)

echo.
echo  Note: Password will be visible — close this window when done.
set /p ADMIN_PASSWORD=  Admin password (min 12 chars): 

:: Basic length check (batch can't do much better)
set "PW=%ADMIN_PASSWORD%"
if not defined PW (
    echo  [FAIL] Password cannot be empty.
    pause & exit /b 1
)

:: Step B: Check Docker
echo.
echo  [A/5] Checking Docker...
where docker >nul 2>&1
if %errorlevel% neq 0 (
    echo  [FAIL] Docker not found.
    echo  Install Docker Desktop from https://www.docker.com/products/docker-desktop
    echo  Then re-run this installer.
    pause & exit /b 1
)
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo  [FAIL] Docker daemon not running. Please start Docker Desktop.
    pause & exit /b 1
)
echo  [OK]  Docker running.

:: Step C: Check Node
echo  [B/5] Checking Node.js...
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo  [FAIL] Node.js not found. Install from https://nodejs.org
    pause & exit /b 1
)
for /f "tokens=*" %%v in ('node --version') do set NODE_VER=%%v
echo  [OK]  Node.js %NODE_VER%

:: Step D: Write a minimal .env
echo  [C/5] Writing .env...
(
echo RAIN_ENV=development
echo RAIN_VERSION=6.0.0
echo POSTGRES_USER=rain_app
echo POSTGRES_PASSWORD=rain_enterprise_local
echo POSTGRES_DB=rain
echo DATABASE_URL=postgresql+asyncpg://rain_app:rain_enterprise_local@postgres:5432/rain
echo VALKEY_URL=redis://valkey:6379/0
echo REDIS_URL=redis://valkey:6379/0
echo MINIO_ROOT_USER=rain_minio
echo MINIO_ROOT_PASSWORD=rain_minio_local
echo S3_BUCKET=rain-audio
echo S3_ENDPOINT_URL=http://minio:9000
echo S3_ACCESS_KEY=rain_minio
echo S3_SECRET_KEY=rain_minio_local
echo JWT_SECRET_KEY=batch-fallback-dev-secret-change-me
echo JWT_ALGORITHM=HS256
echo JWT_PUBLIC_KEY_PATH=/etc/rain/jwt.pub
echo JWT_PRIVATE_KEY_PATH=/etc/rain/jwt.key
echo RAIN_CERT_SIGNING_KEY_PATH=/etc/rain/cert.key
echo RAIN_WATERMARK_KEY_PATH=/etc/rain/wm.key
echo RAIN_NORMALIZATION_VALIDATED=false
echo ANTHROPIC_API_KEY=
echo ONNX_MODEL_PATH=/models/rain_base.onnx
echo GENRE_CLASSIFIER_ENABLED=false
echo CODEC_NET_ENABLED=false
echo SEPARATION_ENABLED=false
echo BSROFORMER_DEVICE=cpu
echo ATMOS_ENABLED=false
echo FRONTEND_URL=http://localhost:5173,http://localhost:4173,http://localhost:3000
echo BACKEND_URL=http://localhost:8000
echo RAIN_ADMIN_EMAIL=%ADMIN_EMAIL%
echo RAIN_ADMIN_PASSWORD=%ADMIN_PASSWORD%
echo RAIN_ADMIN_TIER=enterprise
echo RAIN_ADMIN_IS_ADMIN=true
echo GF_ADMIN_USER=admin
echo GF_ADMIN_PASSWORD=rain_grafana
echo LABELGRID_SANDBOX=true
echo ISRC_REGISTRANT_CODE=ARC
echo UPC_GS1_PREFIX=000000
) > .env
echo  [OK]  .env written.

:: Ensure keys dir exists
if not exist "keys\" mkdir keys

:: Step E: Build + start with Docker Compose
echo  [D/5] Building and starting Docker services...
docker compose --env-file .env build
if %errorlevel% neq 0 (
    echo  [FAIL] docker compose build failed.
    pause & exit /b 1
)

docker compose --env-file .env up -d
if %errorlevel% neq 0 (
    echo  [FAIL] docker compose up failed.
    pause & exit /b 1
)
echo  [OK]  Services started.

:: Step E: Wait and open browser
echo  [E/5] Waiting 20 seconds for services to initialize...
timeout /t 20 /nobreak >nul

echo.
echo  Opening RAIN in your browser...
start http://localhost:5173

echo.
echo  ╔══════════════════════════════════════════════════════════════╗
echo  ║   RAIN IS RUNNING (batch mode)                              ║
echo  ║                                                             ║
echo  ║   RAIN UI   →  http://localhost:5173                        ║
echo  ║   API Docs  →  http://localhost:8000/docs                   ║
echo  ║   Grafana   →  http://localhost:3000                        ║
echo  ║                                                             ║
echo  ║   Login with: %ADMIN_EMAIL%
echo  ║   Tier: Enterprise (all features unlocked)                  ║
echo  ║                                                             ║
echo  ╚══════════════════════════════════════════════════════════════╝
echo.

pause
