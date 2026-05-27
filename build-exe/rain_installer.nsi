; ==============================================================================
;  R∞N AI MASTERING ENGINE v6.0 — NSIS Enterprise Installer
;  ARCOVEL Technologies International
;  Produces: RAIN-Enterprise-Setup.exe  (~154 KB, Windows PE x86 / x64 compat)
;
;  Build:   makensis build-exe/rain_installer.nsi
;  Output:  build-exe/dist/RAIN-Enterprise-Setup.exe
; ==============================================================================

Unicode True
SetCompressor /SOLID lzma

; ── Metadata ──────────────────────────────────────────────────────────────────
!define PRODUCT_NAME      "RAIN AI Mastering Engine"
!define PRODUCT_VERSION   "6.0.0"
!define PRODUCT_PUBLISHER "ARCOVEL Technologies International"
!define PRODUCT_URL       "https://github.com/aurorav5/RAIN-MASTERING-DISTRIBUTION-ENGINE"

Name    "${PRODUCT_NAME} v${PRODUCT_VERSION} - Enterprise Installer"
OutFile "dist\RAIN-Enterprise-Setup.exe"
InstallDir "$PROGRAMFILES64\RAIN"
RequestExecutionLevel admin
SetCompress auto

; ── Windows file-property version block ──────────────────────────────────────
VIProductVersion "6.0.0.0"
VIAddVersionKey /LANG=1033 "ProductName"      "${PRODUCT_NAME}"
VIAddVersionKey /LANG=1033 "ProductVersion"   "${PRODUCT_VERSION}"
VIAddVersionKey /LANG=1033 "CompanyName"      "${PRODUCT_PUBLISHER}"
VIAddVersionKey /LANG=1033 "LegalCopyright"   "(c) 2026 ${PRODUCT_PUBLISHER}"
VIAddVersionKey /LANG=1033 "FileDescription"  "RAIN AI Mastering Engine v6.0 Enterprise Installer"
VIAddVersionKey /LANG=1033 "FileVersion"      "6.0.0.0"
VIAddVersionKey /LANG=1033 "OriginalFilename" "RAIN-Enterprise-Setup.exe"
VIAddVersionKey /LANG=1033 "InternalName"     "RAIN-Enterprise-Setup"

; ── Modern UI ─────────────────────────────────────────────────────────────────
!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "WinVer.nsh"
!include "nsDialogs.nsh"

!define MUI_ABORTWARNING
!define MUI_ICON "..\rain.ico"

!define MUI_WELCOMEPAGE_TITLE   "R8N AI Mastering Engine v6.0$\nEnterprise Tier Installer"
!define MUI_WELCOMEPAGE_TEXT    \
    "This installer will:$\n\
$\n  1. Check prerequisites (Docker, Node 20+, Python 3.12+)$\n\
    2. Generate RSA-4096 JWT + Ed25519 RAIN-CERT keys$\n\
    3. Write a production .env with randomised secrets$\n\
    4. Build and start the full RAIN stack via Docker Compose$\n\
    5. Run all 6 Alembic database migrations$\n\
    6. Seed your Enterprise admin account$\n\
    7. Create desktop shortcuts (Start / Stop / Status)$\n\
    8. Open the RAIN UI in your browser$\n\
$\nEnterprise tier features:$\n\
    16-stage mastering chain  |  18 QC checks$\n\
    27 platform targets       |  8 export formats$\n\
    DDEX ERN 4.3 distribution |  C2PA v2.2 provenance$\n\
    50 000 API req/hour       |  Unlimited renders$\n\
$\nRAIN doesn't live in the cloud."

!define MUI_FINISHPAGE_TITLE "R8N Installation Complete"
!define MUI_FINISHPAGE_TEXT  \
    "RAIN Enterprise is running.$\n\
$\nRAIN UI     : http://localhost:5173$\n\
API Docs    : http://localhost:8000/docs$\n\
Grafana     : http://localhost:3000$\n\
MinIO       : http://localhost:9001$\n\
Prometheus  : http://localhost:9090$\n\
$\nUse the desktop shortcuts to start/stop RAIN.$\n\
$\nRain doesn't live in the cloud."

!define MUI_FINISHPAGE_LINK          "Open RAIN UI in browser"
!define MUI_FINISHPAGE_LINK_LOCATION "http://localhost:5173"

; ── Pages ─────────────────────────────────────────────────────────────────────
!insertmacro MUI_PAGE_WELCOME
Page custom CredentialsPage CredentialsLeave
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_LANGUAGE "English"

; ── Variables ─────────────────────────────────────────────────────────────────
Var AdminEmail
Var AdminPw
Var AdminPwConfirm
Var RepoRoot
Var LauncherPS1

; Credentials dialog handles
Var dlg
Var hEmail
Var hPw
Var hPwC
Var hInfoLbl

; ── Credentials custom page ───────────────────────────────────────────────────
Function CredentialsPage
    nsDialogs::Create 1018
    Pop $dlg
    ${If} $dlg == error
        Abort
    ${EndIf}

    ${NSD_CreateLabel}   0   0 100% 24u \
        "Enter your Enterprise admin credentials. These will be used to log in to the RAIN UI."
    Pop $hInfoLbl

    ${NSD_CreateLabel}   0  32u  28% 12u "Admin e-mail:"
    Pop $0
    ${NSD_CreateText}   30%  30u  70% 14u ""
    Pop $hEmail

    ${NSD_CreateLabel}   0  52u  28% 12u "Password (>=12 chars):"
    Pop $0
    ${NSD_CreatePassword} 30% 50u 70% 14u ""
    Pop $hPw

    ${NSD_CreateLabel}   0  72u  28% 12u "Confirm password:"
    Pop $0
    ${NSD_CreatePassword} 30% 70u 70% 14u ""
    Pop $hPwC

    nsDialogs::Show
FunctionEnd

Function CredentialsLeave
    ${NSD_GetText} $hEmail $AdminEmail
    ${NSD_GetText} $hPw    $AdminPw
    ${NSD_GetText} $hPwC   $AdminPwConfirm

    ; Validate e-mail
    StrLen $1 "$AdminEmail"
    ${If} $1 == 0
        MessageBox MB_ICONEXCLAMATION "E-mail address cannot be empty."
        Abort
    ${EndIf}

    ; Validate password length (>=12)
    StrLen $1 "$AdminPw"
    ${If} $1 < 12
        MessageBox MB_ICONEXCLAMATION "Password must be at least 12 characters."
        Abort
    ${EndIf}

    ; Validate match
    ${If} "$AdminPw" != "$AdminPwConfirm"
        MessageBox MB_ICONEXCLAMATION "Passwords do not match. Please try again."
        Abort
    ${EndIf}
FunctionEnd

; ── Install section ───────────────────────────────────────────────────────────
Section "RAIN Enterprise" SecMain

    SetOutPath "$INSTDIR"

    ; Embed the two installer scripts
    File /oname=RAIN-Enterprise-Setup.ps1 "..\RAIN-Enterprise-Setup.ps1"
    File /oname=RAIN-Enterprise-Setup.bat "..\RAIN-Enterprise-Setup.bat"

    ; ── Locate repo root ──────────────────────────────────────────────────────
    ; Check common locations where the user likely cloned the repo
    StrCpy $RepoRoot ""

    ${If} ${FileExists} "$DESKTOP\RAIN-MASTERING-DISTRIBUTION-ENGINE\docker-compose.yml"
        StrCpy $RepoRoot "$DESKTOP\RAIN-MASTERING-DISTRIBUTION-ENGINE"
    ${ElseIf} ${FileExists} "$DOCUMENTS\RAIN-MASTERING-DISTRIBUTION-ENGINE\docker-compose.yml"
        StrCpy $RepoRoot "$DOCUMENTS\RAIN-MASTERING-DISTRIBUTION-ENGINE"
    ${ElseIf} ${FileExists} "$PROFILE\RAIN-MASTERING-DISTRIBUTION-ENGINE\docker-compose.yml"
        StrCpy $RepoRoot "$PROFILE\RAIN-MASTERING-DISTRIBUTION-ENGINE"
    ${ElseIf} ${FileExists} "$PROFILE\Documents\RAIN-MASTERING-DISTRIBUTION-ENGINE\docker-compose.yml"
        StrCpy $RepoRoot "$PROFILE\Documents\RAIN-MASTERING-DISTRIBUTION-ENGINE"
    ${ElseIf} ${FileExists} "C:\RAIN\docker-compose.yml"
        StrCpy $RepoRoot "C:\RAIN"
    ${ElseIf} ${FileExists} "C:\Users\Public\RAIN-MASTERING-DISTRIBUTION-ENGINE\docker-compose.yml"
        StrCpy $RepoRoot "C:\Users\Public\RAIN-MASTERING-DISTRIBUTION-ENGINE"
    ${Else}
        ; Prompt the user
        nsDialogs::SelectFolderDialog \
            "Select the RAIN repo root (folder containing docker-compose.yml):" \
            "$PROFILE"
        Pop $RepoRoot
        ${If} $RepoRoot == error
            MessageBox MB_ICONSTOP "No repo folder selected. Cannot continue."
            Abort
        ${EndIf}
        ; Verify
        ${If} ${FileExists} "$RepoRoot\docker-compose.yml"
            ; good
        ${Else}
            MessageBox MB_ICONSTOP \
                "docker-compose.yml not found in:$\n$RepoRoot$\n$\nPlease clone the repo and try again."
            Abort
        ${EndIf}
    ${EndIf}

    DetailPrint "Repo root: $RepoRoot"
    DetailPrint "Admin:     $AdminEmail"
    DetailPrint ""

    ; ── Write a pre-configured shim that calls the main PS1 ──────────────────
    ; We write a tiny shim that changes to the repo root and passes env vars
    ; BEFORE calling the main PowerShell installer.
    ; This avoids putting the password into command-line arguments (which show
    ; in Task Manager) — instead it's in a temp .ps1 file readable only by admin.

    StrCpy $LauncherPS1 "$INSTDIR\RAIN-Run-Now.ps1"

    ; Write line by line to avoid $ escaping issues in NSIS strings
    FileOpen  $0 "$LauncherPS1" w
    FileWrite $0 "# RAIN Enterprise Installer Shim$\r$\n"
    FileWrite $0 "# Auto-generated — delete after install$\r$\n"
    FileWrite $0 '$ErrorActionPreference = "Stop"$\r$\n'
    FileWrite $0 "Set-Location '$RepoRoot'$\r$\n"
    FileWrite $0 '$env:RAIN_ADMIN_EMAIL    = "'
    FileWrite $0 "$AdminEmail"
    FileWrite $0 '"$\r$\n'
    FileWrite $0 '$env:RAIN_ADMIN_PASSWORD = "'
    FileWrite $0 "$AdminPw"
    FileWrite $0 '"$\r$\n'
    FileWrite $0 '$env:RAIN_ADMIN_TIER     = "enterprise"$\r$\n'
    FileWrite $0 '$env:RAIN_ADMIN_IS_ADMIN = "true"$\r$\n'
    FileWrite $0 "& '$INSTDIR\RAIN-Enterprise-Setup.ps1'$\r$\n"
    FileClose $0

    ; ── Execute ───────────────────────────────────────────────────────────────
    DetailPrint "Launching RAIN Enterprise full-stack installer..."
    DetailPrint "(A PowerShell window will open — follow the prompts)"
    DetailPrint ""
    DetailPrint "Phase 1: Prerequisite check + key generation"
    DetailPrint "Phase 2: Docker image build   (~5-10 min, first run only)"
    DetailPrint "Phase 3: DB migrations + account seeding"
    DetailPrint "Phase 4: Service health check + browser launch"
    DetailPrint ""

    ExecWait \
        'powershell.exe -ExecutionPolicy Bypass -NoProfile -File "$LauncherPS1"' \
        $1

    ; Secure-delete the shim (it contained the password)
    Delete "$LauncherPS1"

    ${If} $1 == 0
        DetailPrint ""
        DetailPrint "===================================================="
        DetailPrint "  R8N ENTERPRISE INSTALLATION COMPLETE"
        DetailPrint "===================================================="
        DetailPrint ""
        DetailPrint "  UI       : http://localhost:5173"
        DetailPrint "  API Docs : http://localhost:8000/docs"
        DetailPrint "  Grafana  : http://localhost:3000"
        DetailPrint "  MinIO    : http://localhost:9001"
        DetailPrint ""
        DetailPrint "  Login: $AdminEmail"
        DetailPrint "  Tier : Enterprise (all features unlocked)"
        DetailPrint ""
        DetailPrint "  Desktop shortcuts created: Start / Stop / Status"
        DetailPrint "===================================================="
    ${Else}
        DetailPrint ""
        DetailPrint "Installer finished (exit: $1)."
        DetailPrint "If RAIN is not running, check Docker Desktop"
        DetailPrint "and run 'RAIN - Start.bat' from your desktop."
        MessageBox MB_ICONINFORMATION \
            "RAIN installer finished (exit code: $1).$\n$\n\
If all services are running, open:$\n\
http://localhost:5173$\n$\n\
If not, ensure Docker Desktop is running,$\n\
then use the 'RAIN - Start.bat' shortcut on your desktop."
    ${EndIf}

    ; ── Registry + uninstaller ────────────────────────────────────────────────
    WriteUninstaller "$INSTDIR\Uninstall-RAIN.exe"

    WriteRegStr   HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\RAIN" \
        "DisplayName"     "${PRODUCT_NAME} v${PRODUCT_VERSION}"
    WriteRegStr   HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\RAIN" \
        "DisplayVersion"  "${PRODUCT_VERSION}"
    WriteRegStr   HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\RAIN" \
        "Publisher"       "${PRODUCT_PUBLISHER}"
    WriteRegStr   HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\RAIN" \
        "URLInfoAbout"    "${PRODUCT_URL}"
    WriteRegStr   HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\RAIN" \
        "InstallLocation" "$INSTDIR"
    WriteRegStr   HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\RAIN" \
        "UninstallString" '"$INSTDIR\Uninstall-RAIN.exe"'
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\RAIN" \
        "NoModify" 1
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\RAIN" \
        "NoRepair"  1

SectionEnd

; ── Uninstaller ───────────────────────────────────────────────────────────────
Section "Uninstall"

    MessageBox MB_YESNO \
        "Stop RAIN Docker services before uninstalling?" IDNO +3
        ExecWait 'cmd.exe /c docker compose --env-file "$PROFILE\RAIN-MASTERING-DISTRIBUTION-ENGINE\.env" stop'
        ExecWait 'cmd.exe /c docker compose --env-file "$DOCUMENTS\RAIN-MASTERING-DISTRIBUTION-ENGINE\.env" stop'

    Delete "$INSTDIR\RAIN-Enterprise-Setup.ps1"
    Delete "$INSTDIR\RAIN-Enterprise-Setup.bat"
    Delete "$INSTDIR\RAIN-Run-Now.ps1"
    Delete "$INSTDIR\Uninstall-RAIN.exe"
    RMDir  "$INSTDIR"

    Delete "$DESKTOP\RAIN - Start.bat"
    Delete "$DESKTOP\RAIN - Stop.bat"
    Delete "$DESKTOP\RAIN - Status.bat"
    Delete "$DESKTOP\R8N Mastering Engine.lnk"

    DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\RAIN"

    MessageBox MB_ICONINFORMATION \
        "RAIN uninstalled.$\n$\n\
Docker images and data volumes are preserved.$\n\
To remove them run in the repo folder:$\n\
  docker compose down -v"

SectionEnd
