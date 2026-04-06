# ================================================================
#  R∞N AI MASTERING ENGINE v6.0 — One-Click Installer & Launcher
#  ARCOVEL Technologies International
#
#  Right-click this file → "Run with PowerShell"
#  Or: powershell -ExecutionPolicy Bypass -File .\RAIN-Install-and-Run.ps1
# ================================================================

$ErrorActionPreference = "Stop"
$Host.UI.RawUI.WindowTitle = "R∞N AI Mastering Engine v6.0"

function Write-Step($num, $total, $msg) {
    Write-Host "  [$num/$total] " -NoNewline -ForegroundColor Cyan
    Write-Host $msg
}

function Write-Ok($msg) {
    Write-Host "  ✓ " -NoNewline -ForegroundColor Green
    Write-Host $msg
}

function Write-Fail($msg) {
    Write-Host "  ✗ " -NoNewline -ForegroundColor Red
    Write-Host $msg
}

Write-Host ""
Write-Host "  ================================================================" -ForegroundColor DarkCyan
Write-Host "   R∞N AI MASTERING ENGINE v6.0" -ForegroundColor Cyan
Write-Host "   ARCOVEL Technologies International" -ForegroundColor DarkGray
Write-Host ""
Write-Host "   Rain doesn't live in the cloud." -ForegroundColor DarkCyan
Write-Host "  ================================================================" -ForegroundColor DarkCyan
Write-Host ""

# ---------------------------------------------------------------
# Step 1: Check Node.js
# ---------------------------------------------------------------
Write-Step 1 5 "Checking Node.js..."
try {
    $nodeVersion = & node --version 2>$null
    if (-not $nodeVersion) { throw "not found" }
    $major = [int]($nodeVersion -replace 'v','').Split('.')[0]
    if ($major -lt 18) {
        Write-Fail "Node.js $nodeVersion is too old. Need v18+."
        Write-Host "  Download from: https://nodejs.org" -ForegroundColor Yellow
        Read-Host "  Press Enter to exit"
        exit 1
    }
    Write-Ok "Node.js $nodeVersion"
} catch {
    Write-Fail "Node.js not found."
    Write-Host ""
    Write-Host "  Node.js 18+ is required. Install from:" -ForegroundColor Yellow
    Write-Host "  https://nodejs.org/en/download" -ForegroundColor White
    Write-Host ""
    $install = Read-Host "  Open download page? (Y/n)"
    if ($install -ne 'n') {
        Start-Process "https://nodejs.org/en/download"
    }
    Read-Host "  After installing Node.js, run this script again. Press Enter to exit"
    exit 1
}

# ---------------------------------------------------------------
# Step 2: Check project files
# ---------------------------------------------------------------
Write-Step 2 5 "Checking project files..."
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

if (-not (Test-Path "frontend\package.json")) {
    Write-Fail "Cannot find frontend\package.json"
    Write-Host "  Make sure this script is in the rain-blueprint root directory." -ForegroundColor Yellow
    Read-Host "  Press Enter to exit"
    exit 1
}
Write-Ok "Project files found"

# ---------------------------------------------------------------
# Step 3: Install dependencies
# ---------------------------------------------------------------
Write-Step 3 5 "Installing dependencies..."
if (Test-Path "frontend\node_modules\.package-lock.json") {
    Write-Ok "Dependencies already installed (skipping)"
} else {
    Write-Host "  Installing npm packages... (this may take a minute)" -ForegroundColor DarkGray
    Push-Location frontend
    & npm install --no-audit --no-fund 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "npm install failed"
        Pop-Location
        Read-Host "  Press Enter to exit"
        exit 1
    }
    Pop-Location
    Write-Ok "Dependencies installed"
}

# ---------------------------------------------------------------
# Step 4: Build production frontend
# ---------------------------------------------------------------
Write-Step 4 5 "Building production frontend..."
if (Test-Path "frontend\dist\index.html") {
    Write-Ok "Production build exists (skipping — delete frontend\dist to rebuild)"
} else {
    Write-Host "  Building... (this may take 15-30 seconds)" -ForegroundColor DarkGray
    Push-Location frontend
    & npx vite build 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "Build failed"
        Pop-Location
        Read-Host "  Press Enter to exit"
        exit 1
    }
    Pop-Location
    Write-Ok "Build complete"
}

# ---------------------------------------------------------------
# Step 5: Launch
# ---------------------------------------------------------------
Write-Step 5 5 "Starting R∞N..."
Write-Host ""
Write-Host "  ================================================================" -ForegroundColor DarkCyan
Write-Host ""
Write-Host "   R∞N is running at:" -ForegroundColor White
Write-Host ""
Write-Host "     http://localhost:4173" -ForegroundColor Cyan
Write-Host ""
Write-Host "   Opening in your browser..." -ForegroundColor DarkGray
Write-Host ""
Write-Host "   Press Ctrl+C to stop." -ForegroundColor DarkGray
Write-Host ""
Write-Host "  ================================================================" -ForegroundColor DarkCyan
Write-Host ""

# Open browser after short delay
Start-Job -ScriptBlock {
    Start-Sleep -Seconds 3
    Start-Process "http://localhost:4173"
} | Out-Null

# Start server (blocks)
Push-Location frontend
& npx vite preview --host 0.0.0.0 --port 4173
Pop-Location
