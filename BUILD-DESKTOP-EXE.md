# Building RAIN as a Desktop .exe (Windows)

## Option 1: One-Click Script (No Build Required)

Double-click **`RAIN-Install-and-Run.bat`** in the repo root.

This installs dependencies, builds the frontend, starts a local server,
and opens RAIN in your browser. No admin rights needed.

Requirements: **Node.js 18+** from https://nodejs.org

---

## Option 2: PowerShell (Better UX)

Right-click **`RAIN-Install-and-Run.ps1`** → "Run with PowerShell"

Or from terminal:
```powershell
powershell -ExecutionPolicy Bypass -File .\RAIN-Install-and-Run.ps1
```

---

## Option 3: Native Desktop App (.exe via Tauri)

This builds a real Windows `.exe` installer — no browser needed.
RAIN runs as a native desktop app with its own window.

### Prerequisites

1. **Rust** — https://rustup.rs
2. **Node.js 18+** — https://nodejs.org
3. **Visual Studio Build Tools** — https://visualstudio.microsoft.com/visual-cpp-build-tools/
   - Select "Desktop development with C++" workload

### Build Steps

```bash
# 1. Install frontend dependencies
cd frontend
npm install

# 2. Build the frontend
npx vite build

# 3. Install Tauri CLI
cd ../rain-desktop
npm install

# 4. Build the desktop app
npx tauri build
```

The installer will be at:
```
rain-desktop/src-tauri/target/release/bundle/nsis/RAIN_6.0.0_x64-setup.exe
```

### What You Get

- **RAIN_6.0.0_x64-setup.exe** — Windows installer (NSIS)
- **RAIN_6.0.0_x64_en-US.msi** — Windows MSI installer
- Installs to Program Files, creates Start Menu shortcut
- Runs as a native window (WebView2, no browser needed)
- Auto-updates supported via Tauri updater

---

## Option 4: Portable .exe (No Install)

After building with Tauri, the standalone executable is at:
```
rain-desktop/src-tauri/target/release/RAIN.exe
```

Copy this single file anywhere and run it. No installation needed.
