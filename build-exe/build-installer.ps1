# ==============================================================================
#  RAIN Installer .exe Builder
#  Compiles RAIN-Enterprise-Setup.ps1 into a standalone Windows .exe
#  using ps2exe (no NSIS, no external tools required)
#
#  Run this script ONCE on a Windows machine to produce:
#    dist\RAIN-Enterprise-Setup.exe
#
#  Requirements: PowerShell 5.1+, internet access (to fetch ps2exe from PSGallery)
# ==============================================================================
$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "  Building RAIN-Enterprise-Setup.exe ..." -ForegroundColor Cyan
Write-Host ""

# Install ps2exe if not present
if (-not (Get-Module -ListAvailable -Name ps2exe)) {
    Write-Host "  Installing ps2exe from PSGallery..." -ForegroundColor DarkGray
    Install-Module -Name ps2exe -Scope CurrentUser -Force -AllowClobber
}

Import-Module ps2exe

$root    = Split-Path -Parent $PSScriptRoot
$srcPs1  = Join-Path $root "RAIN-Enterprise-Setup.ps1"
$distDir = Join-Path $PSScriptRoot "dist"
$outExe  = Join-Path $distDir "RAIN-Enterprise-Setup.exe"

if (-not (Test-Path $distDir)) { New-Item -ItemType Directory -Path $distDir | Out-Null }

Invoke-ps2exe `
    -InputFile   $srcPs1 `
    -OutputFile  $outExe `
    -Title       "R∞N AI Mastering Engine v6.0 — Enterprise Installer" `
    -Description "RAIN Mastering & Distribution Engine — Enterprise Tier Full-Stack Installer" `
    -Company     "ARCOVEL Technologies International" `
    -Product     "RAIN AI Mastering Engine" `
    -Version     "6.0.0.0" `
    -Copyright   "© 2026 ARCOVEL Technologies International" `
    -RequireAdmin `
    -NoConsole:$false `
    -x64

if (Test-Path $outExe) {
    $size = [math]::Round((Get-Item $outExe).Length / 1KB, 1)
    Write-Host ""
    Write-Host "  ✓ Built: $outExe ($size KB)" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Distribute this single .exe file." -ForegroundColor DarkGray
    Write-Host "  Recipients double-click it — no other files needed." -ForegroundColor DarkGray
    Write-Host ""
} else {
    Write-Host "  Build failed — check ps2exe output above." -ForegroundColor Red
    exit 1
}
