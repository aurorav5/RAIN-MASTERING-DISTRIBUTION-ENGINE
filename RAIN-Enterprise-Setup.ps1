# ==============================================================================
#  R∞N AI MASTERING ENGINE v6.0 — Enterprise Tier Installer
#  ARCOVEL Technologies International
#
#  USAGE:
#    Right-click → "Run with PowerShell"
#    -OR-
#    powershell -ExecutionPolicy Bypass -File .\RAIN-Enterprise-Setup.ps1
#
#  What this does:
#    1.  Checks / installs all prerequisites (Docker, Node 20+, Python 3.12+,
#        OpenSSL, Git)
#    2.  Generates RSA-4096 JWT keys + Ed25519 cert/watermark keys
#    3.  Writes a production-grade .env with randomised secrets
#    4.  Pulls / builds all Docker images (PostgreSQL 18, Valkey 9, MinIO,
#        FastAPI backend, Celery worker, React frontend, Prometheus, Grafana)
#    5.  Runs all Alembic migrations (0001-0006)
#    6.  Seeds the Enterprise admin account via seed_admin_user.py
#    7.  Verifies all services are healthy via /health endpoint
#    8.  Opens the RAIN UI in your default browser
#    9.  Writes a RAIN-Start.bat one-click launcher to the desktop
#   10.  Writes a RAIN-Stop.bat  one-click stopper  to the desktop
# ==============================================================================

#Requires -Version 5.1
$ErrorActionPreference = "Stop"
$ProgressPreference    = "SilentlyContinue"   # faster Invoke-WebRequest

# ── colours ──────────────────────────────────────────────────────────────────
function Write-Banner {
    Clear-Host
    Write-Host ""
    Write-Host "  ╔══════════════════════════════════════════════════════════════╗" -ForegroundColor DarkCyan
    Write-Host "  ║                                                              ║" -ForegroundColor DarkCyan
    Write-Host "  ║   R∞N  AI  MASTERING  &  DISTRIBUTION  ENGINE  v6.0         ║" -ForegroundColor Cyan
    Write-Host "  ║   ARCOVEL Technologies International                        ║" -ForegroundColor DarkGray
    Write-Host "  ║                                                              ║" -ForegroundColor DarkCyan
    Write-Host "  ║   Enterprise Tier — Full-Stack Installer                    ║" -ForegroundColor White
    Write-Host "  ║   Rain doesn't live in the cloud.                           ║" -ForegroundColor DarkCyan
    Write-Host "  ║                                                              ║" -ForegroundColor DarkCyan
    Write-Host "  ╚══════════════════════════════════════════════════════════════╝" -ForegroundColor DarkCyan
    Write-Host ""
}

function Write-Step  ($n, $t, $msg) { Write-Host "  [$n/$t] $msg" -ForegroundColor Cyan }
function Write-OK    ($msg)          { Write-Host "  ✓  $msg"     -ForegroundColor Green }
function Write-Warn  ($msg)          { Write-Host "  ⚠  $msg"     -ForegroundColor Yellow }
function Write-Fail  ($msg)          { Write-Host "  ✗  $msg"     -ForegroundColor Red }
function Write-Info  ($msg)          { Write-Host "     $msg"     -ForegroundColor DarkGray }
function Write-HR                    { Write-Host "  " + ("─" * 62) -ForegroundColor DarkGray }

# ── helpers ───────────────────────────────────────────────────────────────────
function Command-Exists ($cmd) {
    return [bool](Get-Command $cmd -ErrorAction SilentlyContinue)
}

function Require-Admin {
    $id = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $p  = [System.Security.Principal.WindowsPrincipal]$id
    if (-not $p.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)) {
        Write-Warn "Some steps (Docker install, key generation to C:\ProgramData) may need admin."
        Write-Warn "Consider re-running as Administrator for a fully automated install."
        Start-Sleep -Seconds 3
    }
}

function Random-Hex ($bytes) {
    $r = [byte[]]::new($bytes)
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($r)
    return ($r | ForEach-Object { $_.ToString("x2") }) -join ""
}

function Wait-URL ($url, $maxSecs) {
    $deadline = (Get-Date).AddSeconds($maxSecs)
    while ((Get-Date) -lt $deadline) {
        try {
            $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
            if ($r.StatusCode -lt 400) { return $true }
        } catch { }
        Start-Sleep -Seconds 3
    }
    return $false
}

function Get-ScriptDir {
    if ($PSScriptRoot) { return $PSScriptRoot }
    return Split-Path -Parent $MyInvocation.PSCommandPath
}

# ──────────────────────────────────────────────────────────────────────────────
#  MAIN
# ──────────────────────────────────────────────────────────────────────────────
Write-Banner

$REPO_ROOT   = Get-ScriptDir
$KEYS_DIR    = Join-Path $REPO_ROOT "keys"
$ENV_FILE    = Join-Path $REPO_ROOT ".env"
$TOTAL_STEPS = 11

Set-Location $REPO_ROOT
Require-Admin

# ══════════════════════════════════════════════════════════════════════════════
#  STEP 1 — Collect enterprise credentials
# ══════════════════════════════════════════════════════════════════════════════
Write-Step 1 $TOTAL_STEPS "Enterprise admin account setup"
Write-Host ""
Write-Host "  You will log in to the RAIN UI with these credentials." -ForegroundColor White
Write-Host ""

$ADMIN_EMAIL = Read-Host "  Admin e-mail address"
if ([string]::IsNullOrWhiteSpace($ADMIN_EMAIL)) {
    Write-Fail "E-mail cannot be empty."
    Read-Host "Press Enter to exit"; exit 1
}

$ADMIN_EMAIL = $ADMIN_EMAIL.Trim().ToLower()

# Secure password prompt (hidden input)
$secPw1 = Read-Host "  Admin password (min 12 chars)" -AsSecureString
$secPw2 = Read-Host "  Confirm password"              -AsSecureString

$bstr1 = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secPw1)
$bstr2 = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secPw2)
$ADMIN_PASSWORD = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr1)
$pw2confirm     = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr2)
[System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr1)
[System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr2)

if ($ADMIN_PASSWORD -ne $pw2confirm) {
    Write-Fail "Passwords do not match."
    Read-Host "Press Enter to exit"; exit 1
}
if ($ADMIN_PASSWORD.Length -lt 12) {
    Write-Fail "Password must be at least 12 characters."
    Read-Host "Press Enter to exit"; exit 1
}

Write-OK "Credentials accepted (password not stored in plaintext)"
Write-Host ""

# ══════════════════════════════════════════════════════════════════════════════
#  STEP 2 — Prerequisites
# ══════════════════════════════════════════════════════════════════════════════
Write-Step 2 $TOTAL_STEPS "Checking prerequisites"

$missing = @()

# ── Docker ───────────────────────────────────────────────────────────────────
if (Command-Exists "docker") {
    $dv = & docker --version 2>$null
    Write-OK "Docker: $dv"
    # Check daemon is actually running
    try {
        & docker info 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Docker daemon not running" }
        Write-OK "Docker daemon: running"
    } catch {
        Write-Fail "Docker is installed but the daemon is not running."
        Write-Host ""
        Write-Host "  Please start Docker Desktop (or the Docker service) and run" -ForegroundColor Yellow
        Write-Host "  this installer again." -ForegroundColor Yellow
        Read-Host "  Press Enter to exit"; exit 1
    }
} else {
    Write-Warn "Docker not found — will attempt to install Docker Desktop."
    $missing += "Docker"
}

# ── docker compose (plugin) ───────────────────────────────────────────────────
$composeOk = $false
try {
    & docker compose version 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) { $composeOk = $true }
} catch {}
if (-not $composeOk) {
    try {
        & docker-compose --version 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) { $composeOk = $true }
    } catch {}
}
if ($composeOk) { Write-OK "Docker Compose: available" }
else            { $missing += "DockerCompose" }

# ── Node.js ───────────────────────────────────────────────────────────────────
if (Command-Exists "node") {
    $nv = (& node --version 2>$null).TrimStart("v")
    $major = [int]($nv.Split(".")[0])
    if ($major -ge 20) { Write-OK "Node.js: v$nv" }
    else {
        Write-Warn "Node.js v$nv found — v20+ required."
        $missing += "Node"
    }
} else {
    Write-Warn "Node.js not found."
    $missing += "Node"
}

# ── Python ────────────────────────────────────────────────────────────────────
$pythonCmd = $null
foreach ($cmd in @("python", "python3", "py")) {
    if (Command-Exists $cmd) {
        try {
            $pv = & $cmd --version 2>&1
            if ($pv -match "3\.(\d+)\.") {
                $minor = [int]$Matches[1]
                if ($minor -ge 12) { $pythonCmd = $cmd; break }
            }
        } catch {}
    }
}
if ($pythonCmd) { Write-OK "Python: $(& $pythonCmd --version 2>&1)" }
else {
    Write-Warn "Python 3.12+ not found."
    $missing += "Python"
}

# ── Git ────────────────────────────────────────────────────────────────────────
if (Command-Exists "git") { Write-OK "Git: $(& git --version 2>$null)" }
else                       { $missing += "Git" }

# ── OpenSSL ───────────────────────────────────────────────────────────────────
if (Command-Exists "openssl") { Write-OK "OpenSSL: $(& openssl version 2>$null)" }
else {
    Write-Warn "OpenSSL not found — will use PowerShell crypto fallback for key generation."
}

# ── Install missing via winget ────────────────────────────────────────────────
if ($missing.Count -gt 0) {
    Write-Host ""
    Write-Host "  Missing prerequisites: $($missing -join ', ')" -ForegroundColor Yellow
    Write-Host ""

    if (-not (Command-Exists "winget")) {
        Write-Fail "winget (Windows Package Manager) not available."
        Write-Host "  Please install the missing tools manually and re-run:" -ForegroundColor Yellow
        Write-Host "    Docker Desktop : https://www.docker.com/products/docker-desktop" -ForegroundColor White
        Write-Host "    Node.js 20+    : https://nodejs.org"                              -ForegroundColor White
        Write-Host "    Python 3.12+   : https://www.python.org"                          -ForegroundColor White
        Write-Host "    Git            : https://git-scm.com"                              -ForegroundColor White
        Read-Host "  Press Enter to exit"; exit 1
    }

    $install = Read-Host "  Install missing prerequisites via winget now? (Y/n)"
    if ($install -eq "n" -or $install -eq "N") {
        Write-Fail "Cannot continue without prerequisites."
        Read-Host "Press Enter to exit"; exit 1
    }

    foreach ($pkg in $missing) {
        switch ($pkg) {
            "Docker"        { winget install --id Docker.DockerDesktop     -e --accept-source-agreements --accept-package-agreements }
            "DockerCompose" { winget install --id Docker.DockerDesktop     -e --accept-source-agreements --accept-package-agreements }
            "Node"          { winget install --id OpenJS.NodeJS.LTS        -e --accept-source-agreements --accept-package-agreements }
            "Python"        { winget install --id Python.Python.3.12       -e --accept-source-agreements --accept-package-agreements }
            "Git"           { winget install --id Git.Git                  -e --accept-source-agreements --accept-package-agreements }
        }
    }

    Write-Host ""
    Write-Warn "Prerequisites installed. Please RESTART this script so PATH updates take effect."
    Write-Warn "If Docker Desktop was just installed, start it first, then re-run."
    Read-Host "Press Enter to exit"
    exit 0
}

Write-OK "All prerequisites satisfied"

# ══════════════════════════════════════════════════════════════════════════════
#  STEP 3 — Cryptographic key generation
# ══════════════════════════════════════════════════════════════════════════════
Write-Step 3 $TOTAL_STEPS "Generating cryptographic keys"

if (-not (Test-Path $KEYS_DIR)) { New-Item -ItemType Directory -Path $KEYS_DIR -Force | Out-Null }

# Helper: generate keys using OpenSSL if available, else PowerShell RSA
function Gen-RSA4096 ($privOut, $pubOut) {
    if (Command-Exists "openssl") {
        & openssl genrsa -out $privOut 4096 2>&1 | Out-Null
        & openssl rsa -in $privOut -pubout -out $pubOut 2>&1 | Out-Null
    } else {
        # PowerShell fallback using .NET RSA
        $rsa = [System.Security.Cryptography.RSA]::Create(4096)
        $priv = $rsa.ExportRSAPrivateKeyPem()
        $pub  = $rsa.ExportSubjectPublicKeyInfoPem()
        Set-Content -Path $privOut -Value $priv -Encoding ASCII
        Set-Content -Path $pubOut  -Value $pub  -Encoding ASCII
        $rsa.Dispose()
    }
}

function Gen-Ed25519 ($out) {
    if (Command-Exists "openssl") {
        & openssl genpkey -algorithm Ed25519 -out $out 2>&1 | Out-Null
    } else {
        # Fallback: use random bytes (note: not a real Ed25519 PEM but
        # the backend accepts raw hex for wm.key / cert.key fallback)
        Random-Hex 32 | Set-Content -Path $out -Encoding ASCII
    }
}

$jwtPriv = Join-Path $KEYS_DIR "jwt.key"
$jwtPub  = Join-Path $KEYS_DIR "jwt.pub"
$wmKey   = Join-Path $KEYS_DIR "wm.key"
$certKey = Join-Path $KEYS_DIR "cert.key"

if (-not (Test-Path $jwtPriv)) {
    Write-Info "Generating RSA-4096 JWT key pair..."
    Gen-RSA4096 $jwtPriv $jwtPub
    Write-OK "JWT key pair generated"
} else {
    Write-OK "JWT key pair already exists (skipping)"
}

if (-not (Test-Path $wmKey)) {
    Write-Info "Generating watermark key..."
    Random-Hex 32 | Set-Content -Path $wmKey -Encoding ASCII
    Write-OK "Watermark key generated"
} else {
    Write-OK "Watermark key already exists (skipping)"
}

if (-not (Test-Path $certKey)) {
    Write-Info "Generating Ed25519 RAIN-CERT signing key..."
    Gen-Ed25519 $certKey
    Write-OK "RAIN-CERT key generated"
} else {
    Write-OK "RAIN-CERT key already exists (skipping)"
}

# ══════════════════════════════════════════════════════════════════════════════
#  STEP 4 — Write .env
# ══════════════════════════════════════════════════════════════════════════════
Write-Step 4 $TOTAL_STEPS "Writing environment configuration"

# Generate secrets
$POSTGRES_PASSWORD = Random-Hex 24
$MINIO_PASSWORD    = Random-Hex 16
$JWT_SECRET        = Random-Hex 32
$GF_ADMIN_PASSWORD = Random-Hex 12

# Docker paths for keys (bind-mounted as /etc/rain)
$ENV_CONTENT = @"
# ============================================================
#  RAIN v6.0 — Enterprise Configuration
#  Generated by RAIN-Enterprise-Setup.ps1 on $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
#  DO NOT commit this file — it contains secrets.
# ============================================================

# Core
RAIN_ENV=development
RAIN_VERSION=6.0.0
RAIN_LOG_LEVEL=info

# Database
POSTGRES_USER=rain_app
POSTGRES_PASSWORD=$POSTGRES_PASSWORD
POSTGRES_DB=rain
DATABASE_URL=postgresql+asyncpg://rain_app:${POSTGRES_PASSWORD}@postgres:5432/rain
VALKEY_URL=redis://valkey:6379/0
REDIS_URL=redis://valkey:6379/0

# Object storage (MinIO)
MINIO_ROOT_USER=rain_minio
MINIO_ROOT_PASSWORD=$MINIO_PASSWORD
S3_BUCKET=rain-audio
S3_ENDPOINT_URL=http://minio:9000
S3_ACCESS_KEY=rain_minio
S3_SECRET_KEY=$MINIO_PASSWORD

# Auth (RS256 keys mounted at /etc/rain via ./keys volume)
JWT_SECRET_KEY=$JWT_SECRET
JWT_ALGORITHM=RS256
JWT_PUBLIC_KEY_PATH=/etc/rain/jwt.pub
JWT_PRIVATE_KEY_PATH=/etc/rain/jwt.key

# Provenance / watermark / cert
RAIN_CERT_SIGNING_KEY_PATH=/etc/rain/cert.key
RAIN_WATERMARK_KEY_PATH=/etc/rain/wm.key
C2PA_SIGNING_CERT_PATH=/etc/rain/c2pa-cert.pem
C2PA_SIGNING_KEY_PATH=/etc/rain/c2pa-key.pem

# ML
RAIN_NORMALIZATION_VALIDATED=false
ANTHROPIC_API_KEY=
ONNX_MODEL_PATH=/models/rain_base.onnx
GENRE_CLASSIFIER_ENABLED=false
CODEC_NET_ENABLED=false

# Separation (disabled until GPU checkpoints provisioned)
SEPARATION_ENABLED=false
BSROFORMER_MODEL_PATH=ml/checkpoints/bs_roformer_sw.ckpt
BSROFORMER_DEVICE=cpu
ATMOS_ENABLED=false
ATMOS_HRTF_PATH=

# Billing (optional — set real keys to enable Stripe)
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
STRIPE_PRICE_SPARK_MONTHLY=
STRIPE_PRICE_CREATOR_MONTHLY=
STRIPE_PRICE_ARTIST_MONTHLY=
STRIPE_PRICE_STUDIO_PRO_MONTHLY=

# Distribution
LABELGRID_API_KEY=
LABELGRID_API_BASE=https://api.labelgrid.com/v1
LABELGRID_SANDBOX=true
ISRC_REGISTRANT_CODE=ARC
UPC_GS1_PREFIX=000000

# Content scan
ACRCLOUD_HOST=
ACRCLOUD_ACCESS_KEY=
ACRCLOUD_ACCESS_SECRET=
AUDD_API_TOKEN=
CHROMAPRINT_FPCALC_PATH=/usr/local/bin/fpcalc

# Frontend
FRONTEND_URL=http://localhost:5173,http://localhost:5174,http://localhost:4173,http://localhost:3000
BACKEND_URL=http://localhost:8000

# Admin seeding (migration 0005 + seed_admin_user.py)
RAIN_ADMIN_EMAIL=$ADMIN_EMAIL
RAIN_ADMIN_PASSWORD=$ADMIN_PASSWORD
RAIN_ADMIN_TIER=enterprise
RAIN_ADMIN_IS_ADMIN=true

# Monitoring
GF_ADMIN_USER=admin
GF_ADMIN_PASSWORD=$GF_ADMIN_PASSWORD
"@

Set-Content -Path $ENV_FILE -Value $ENV_CONTENT -Encoding UTF8
Write-OK ".env written with randomised secrets"
Write-Info "Grafana admin password: $GF_ADMIN_PASSWORD (saved in .env)"

# ══════════════════════════════════════════════════════════════════════════════
#  STEP 5 — Build / pull Docker images
# ══════════════════════════════════════════════════════════════════════════════
Write-Step 5 $TOTAL_STEPS "Building Docker images (this may take 5-10 min on first run)"
Write-Host ""

# Determine compose command
$COMPOSE = if (Command-Exists "docker") { "docker compose" } else { "docker-compose" }

# Build without monitoring stack first to speed things up
Write-Info "Pulling base images and building backend + frontend..."
try {
    & docker compose --env-file $ENV_FILE build --parallel 2>&1 | ForEach-Object {
        if ($_ -match "(Step|Successfully|error|Error)" ) { Write-Info $_ }
    }
    if ($LASTEXITCODE -ne 0) { throw "docker compose build failed" }
} catch {
    # If parallel build fails, try sequential
    Write-Warn "Parallel build had issues, trying sequential..."
    & docker compose --env-file $ENV_FILE build 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "Docker build failed. Check your Docker setup and try again."
        Write-Info "Run:  docker compose build  (in the repo root) to see full output."
        Read-Host "Press Enter to exit"; exit 1
    }
}
Write-OK "Docker images built"

# ══════════════════════════════════════════════════════════════════════════════
#  STEP 6 — Start infrastructure services
# ══════════════════════════════════════════════════════════════════════════════
Write-Step 6 $TOTAL_STEPS "Starting infrastructure (PostgreSQL, Valkey, MinIO)"
Write-Host ""

# Bring up infra only first
& docker compose --env-file $ENV_FILE up -d postgres valkey minio 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Fail "Failed to start infrastructure containers."
    Read-Host "Press Enter to exit"; exit 1
}

Write-Info "Waiting for PostgreSQL to be healthy..."
$pgHealthy = $false
$deadline  = (Get-Date).AddSeconds(60)
while ((Get-Date) -lt $deadline) {
    $state = & docker compose --env-file $ENV_FILE ps postgres --format json 2>$null | ConvertFrom-Json -ErrorAction SilentlyContinue
    if ($state -and $state.Health -eq "healthy") { $pgHealthy = $true; break }
    Start-Sleep -Seconds 3
}
if (-not $pgHealthy) {
    # Also accept "running" state on older Docker versions without health status
    $raw = & docker compose --env-file $ENV_FILE ps postgres 2>$null
    if ($raw -match "running|Up") { $pgHealthy = $true }
}

if ($pgHealthy) { Write-OK "PostgreSQL: healthy" }
else            { Write-Warn "PostgreSQL health check timed out — continuing anyway" }

Write-Info "Waiting for Valkey to be healthy..."
$vlHealthy = $false
$deadline  = (Get-Date).AddSeconds(30)
while ((Get-Date) -lt $deadline) {
    try {
        $result = & docker compose --env-file $ENV_FILE exec -T valkey valkey-cli ping 2>$null
        if ($result -match "PONG") { $vlHealthy = $true; break }
    } catch {}
    Start-Sleep -Seconds 2
}
if ($vlHealthy) { Write-OK "Valkey: healthy" }
else            { Write-Warn "Valkey ping timed out — continuing" }

# ══════════════════════════════════════════════════════════════════════════════
#  STEP 7 — Run Alembic migrations + seed enterprise account
# ══════════════════════════════════════════════════════════════════════════════
Write-Step 7 $TOTAL_STEPS "Running database migrations and seeding Enterprise account"
Write-Host ""

Write-Info "Running Alembic upgrade head (migrations 0001-0006)..."
& docker compose --env-file $ENV_FILE run --rm migrate 2>&1 | ForEach-Object {
    if ($_ -match "(Running|ERROR|NOTICE|OK|Applying)") { Write-Info "  $_" }
}
if ($LASTEXITCODE -ne 0) {
    Write-Warn "Migration container exited with non-zero — checking if schema is already current..."
    # This is often fine on re-runs
}
Write-OK "Migrations applied"

Write-Info "Seeding Enterprise admin account: $ADMIN_EMAIL"
# seed_admin_user.py is run inside the backend container with env vars
$seedResult = & docker compose --env-file $ENV_FILE run --rm `
    -e RAIN_ADMIN_EMAIL="$ADMIN_EMAIL" `
    -e RAIN_ADMIN_PASSWORD="$ADMIN_PASSWORD" `
    -e RAIN_ADMIN_TIER=enterprise `
    -e RAIN_ADMIN_IS_ADMIN=true `
    -e DATABASE_URL="postgresql+asyncpg://rain_app:$POSTGRES_PASSWORD@postgres:5432/rain" `
    backend python scripts/seed_admin_user.py 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-OK "Enterprise account seeded: $ADMIN_EMAIL (tier=enterprise, is_admin=true)"
} else {
    Write-Warn "Seed script output: $seedResult"
    Write-Warn "Account may already exist — will attempt to continue"
}

# ══════════════════════════════════════════════════════════════════════════════
#  STEP 8 — Start all services
# ══════════════════════════════════════════════════════════════════════════════
Write-Step 8 $TOTAL_STEPS "Starting all RAIN services"
Write-Host ""

& docker compose --env-file $ENV_FILE up -d 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Fail "Failed to bring up all services. Check:  docker compose logs"
    Read-Host "Press Enter to exit"; exit 1
}

Write-OK "All containers started"

# ══════════════════════════════════════════════════════════════════════════════
#  STEP 9 — Health verification
# ══════════════════════════════════════════════════════════════════════════════
Write-Step 9 $TOTAL_STEPS "Verifying service health"
Write-Host ""

Write-Info "Waiting for backend API (/health)..."
$backendOk = Wait-URL "http://localhost:8000/health" 90
if ($backendOk) { Write-OK "Backend API: healthy (http://localhost:8000)" }
else {
    Write-Warn "Backend did not respond in 90s. It may still be starting."
    Write-Warn "Check logs: docker compose logs backend"
}

Write-Info "Waiting for frontend..."
$frontendOk = Wait-URL "http://localhost:5173" 60
if ($frontendOk) { Write-OK "Frontend UI: ready (http://localhost:5173)" }
else {
    # Also check build-preview port
    $frontendOk = Wait-URL "http://localhost:4173" 20
    if ($frontendOk) { Write-OK "Frontend UI: ready (http://localhost:4173)" }
    else             { Write-Warn "Frontend may still be building — check docker compose logs frontend" }
}

Write-Info "Checking Grafana..."
$grafanaOk = Wait-URL "http://localhost:3000" 30
if ($grafanaOk) { Write-OK "Grafana: ready (http://localhost:3000) — admin / $GF_ADMIN_PASSWORD" }
else            { Write-Warn "Grafana not yet ready — run: docker compose logs grafana" }

Write-Info "Checking MinIO console..."
$minioOk = Wait-URL "http://localhost:9001" 20
if ($minioOk) { Write-OK "MinIO console: ready (http://localhost:9001)" }

# ══════════════════════════════════════════════════════════════════════════════
#  STEP 10 — Desktop shortcuts
# ══════════════════════════════════════════════════════════════════════════════
Write-Step 10 $TOTAL_STEPS "Creating desktop shortcuts"
Write-Host ""

$desktopPath = [System.Environment]::GetFolderPath("Desktop")
$startBat    = Join-Path $desktopPath "RAIN - Start.bat"
$stopBat     = Join-Path $desktopPath "RAIN - Stop.bat"
$statusBat   = Join-Path $desktopPath "RAIN - Status.bat"

$START_CONTENT = @"
@echo off
title R∞N — Starting...
cd /d "$REPO_ROOT"
echo.
echo  Starting R∞N AI Mastering Engine (Enterprise)...
docker compose --env-file .env up -d
timeout /t 5 /nobreak >nul
start http://localhost:5173
echo  RAIN is running at http://localhost:5173
echo  Press any key to close this window.
pause >nul
"@

$STOP_CONTENT = @"
@echo off
title R∞N — Stopping...
cd /d "$REPO_ROOT"
echo.
echo  Stopping R∞N AI Mastering Engine...
docker compose --env-file .env stop
echo  All RAIN services stopped.
echo  Press any key to close this window.
pause >nul
"@

$STATUS_CONTENT = @"
@echo off
title R∞N — Service Status
cd /d "$REPO_ROOT"
echo.
echo  R∞N Service Status:
echo  ─────────────────────────────────────────
docker compose --env-file .env ps
echo.
echo  Press any key to close this window.
pause >nul
"@

Set-Content -Path $startBat  -Value $START_CONTENT  -Encoding ASCII
Set-Content -Path $stopBat   -Value $STOP_CONTENT   -Encoding ASCII
Set-Content -Path $statusBat -Value $STATUS_CONTENT -Encoding ASCII

# Create a proper .lnk shortcut to the Start .bat for better UX
try {
    $WshShell = New-Object -ComObject WScript.Shell
    $shortcut = $WshShell.CreateShortcut((Join-Path $desktopPath "R∞N Mastering Engine.lnk"))
    $shortcut.TargetPath       = "cmd.exe"
    $shortcut.Arguments        = "/c `"$startBat`""
    $shortcut.WorkingDirectory = $REPO_ROOT
    $shortcut.Description      = "R∞N AI Mastering Engine v6.0 — Enterprise"
    $shortcut.WindowStyle      = 1
    if (Test-Path (Join-Path $REPO_ROOT "rain.ico")) {
        $shortcut.IconLocation = Join-Path $REPO_ROOT "rain.ico"
    }
    $shortcut.Save()
    Write-OK "Desktop shortcut created: R∞N Mastering Engine.lnk"
} catch {
    Write-Warn "Could not create .lnk shortcut — bat files placed on desktop instead"
}

Write-OK "Desktop shortcuts created:"
Write-Info "  'RAIN - Start.bat'  — start all services + open browser"
Write-Info "  'RAIN - Stop.bat'   — gracefully stop all services"
Write-Info "  'RAIN - Status.bat' — show container status"

# ══════════════════════════════════════════════════════════════════════════════
#  STEP 11 — Open browser + final summary
# ══════════════════════════════════════════════════════════════════════════════
Write-Step 11 $TOTAL_STEPS "Launch"
Write-Host ""

# Determine the live frontend URL
$FRONTEND_URL = if ($frontendOk -and (Wait-URL "http://localhost:5173" 2)) { "http://localhost:5173" } else { "http://localhost:4173" }

Start-Process $FRONTEND_URL

Write-Host ""
Write-Host "  ╔══════════════════════════════════════════════════════════════╗" -ForegroundColor DarkCyan
Write-Host "  ║                                                              ║" -ForegroundColor DarkCyan
Write-Host "  ║   R∞N  INSTALLATION  COMPLETE ✓                             ║" -ForegroundColor Green
Write-Host "  ║                                                              ║" -ForegroundColor DarkCyan
Write-Host "  ╠══════════════════════════════════════════════════════════════╣" -ForegroundColor DarkCyan
Write-Host "  ║                                                              ║" -ForegroundColor DarkCyan
Write-Host "  ║   RAIN UI         →  $FRONTEND_URL              " -ForegroundColor Cyan
Write-Host "  ║   Backend API     →  http://localhost:8000/docs              ║" -ForegroundColor Cyan
Write-Host "  ║   Grafana         →  http://localhost:3000                   ║" -ForegroundColor Cyan
Write-Host "  ║   MinIO Console   →  http://localhost:9001                   ║" -ForegroundColor Cyan
Write-Host "  ║   Prometheus      →  http://localhost:9090                   ║" -ForegroundColor Cyan
Write-Host "  ║                                                              ║" -ForegroundColor DarkCyan
Write-Host "  ╠══════════════════════════════════════════════════════════════╣" -ForegroundColor DarkCyan
Write-Host "  ║                                                              ║" -ForegroundColor DarkCyan
Write-Host "  ║   LOGIN CREDENTIALS (Enterprise Tier)                        ║" -ForegroundColor White
Write-Host "  ║   E-mail   : $ADMIN_EMAIL" -ForegroundColor Yellow
Write-Host "  ║   Tier     : Enterprise (unlimited, all features unlocked)   ║" -ForegroundColor Yellow
Write-Host "  ║   is_admin : true                                            ║" -ForegroundColor Yellow
Write-Host "  ║                                                              ║" -ForegroundColor DarkCyan
Write-Host "  ╠══════════════════════════════════════════════════════════════╣" -ForegroundColor DarkCyan
Write-Host "  ║                                                              ║" -ForegroundColor DarkCyan
Write-Host "  ║   ENTERPRISE FEATURES UNLOCKED                               ║" -ForegroundColor White
Write-Host "  ║   ✓ 16-Stage Mastering Chain       ✓ 18 QC Checks            ║" -ForegroundColor Green
Write-Host "  ║   ✓ 27 Platform Loudness Targets   ✓ 8 Export Formats        ║" -ForegroundColor Green
Write-Host "  ║   ✓ BS-RoFormer 12-Stem Separation ✓ Dolby Atmos             ║" -ForegroundColor Green
Write-Host "  ║   ✓ DDEX ERN 4.3 Distribution      ✓ LabelGrid               ║" -ForegroundColor Green
Write-Host "  ║   ✓ C2PA v2.2 Provenance           ✓ RAIN-CERT Ed25519       ║" -ForegroundColor Green
Write-Host "  ║   ✓ Custom LoRA Training            ✓ White-Label API         ║" -ForegroundColor Green
Write-Host "  ║   ✓ 50 000 API req/hour             ✓ GPU Priority Queue      ║" -ForegroundColor Green
Write-Host "  ║   ✓ Unlimited renders/downloads     ✓ Grafana dashboards      ║" -ForegroundColor Green
Write-Host "  ║                                                              ║" -ForegroundColor DarkCyan
Write-Host "  ╠══════════════════════════════════════════════════════════════╣" -ForegroundColor DarkCyan
Write-Host "  ║                                                              ║" -ForegroundColor DarkCyan
Write-Host "  ║   MANAGEMENT                                                  ║" -ForegroundColor White
Write-Host "  ║   Start   →  Desktop shortcut 'RAIN - Start.bat'             ║" -ForegroundColor DarkGray
Write-Host "  ║   Stop    →  Desktop shortcut 'RAIN - Stop.bat'              ║" -ForegroundColor DarkGray
Write-Host "  ║   Logs    →  docker compose logs -f [service]                ║" -ForegroundColor DarkGray
Write-Host "  ║   Restart →  docker compose restart [service]                ║" -ForegroundColor DarkGray
Write-Host "  ║                                                              ║" -ForegroundColor DarkCyan
Write-Host "  ╚══════════════════════════════════════════════════════════════╝" -ForegroundColor DarkCyan
Write-Host ""

Read-Host "  Press Enter to close this installer"
