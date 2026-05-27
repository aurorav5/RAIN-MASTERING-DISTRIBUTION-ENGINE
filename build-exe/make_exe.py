"""
RAIN Enterprise Installer — .exe Builder
=========================================
This script embeds RAIN-Enterprise-Setup.ps1 into a self-contained
Python-based Windows executable using PyInstaller.

The resulting RAIN-Enterprise-Setup.exe:
  - Is a genuine Windows PE .exe (not a renamed script)
  - Contains the full PowerShell installer as an embedded resource
  - Extracts and runs it at launch time
  - Requires no external files, repos, or Python on the target machine
  - Is ~12 MB (PyInstaller bootloader + embedded PS1)

Usage (run on Windows):
    pip install pyinstaller
    python build-exe/make_exe.py

Output: build-exe/dist/RAIN-Enterprise-Setup.exe
"""
import os, sys, subprocess, textwrap, shutil
from pathlib import Path

REPO_ROOT   = Path(__file__).parent.parent.resolve()
BUILD_DIR   = Path(__file__).parent.resolve()
PS1_SOURCE  = REPO_ROOT / "RAIN-Enterprise-Setup.ps1"
STUB_PY     = BUILD_DIR / "_stub_launcher.py"
ICON_FILE   = REPO_ROOT / "rain.ico"
DIST_DIR    = BUILD_DIR / "dist"
SPEC_FILE   = BUILD_DIR / "RAIN-Enterprise-Setup.spec"

def main():
    if not PS1_SOURCE.exists():
        sys.exit(f"[ERROR] Source not found: {PS1_SOURCE}")

    print(f"[INFO] Reading installer script ({PS1_SOURCE.stat().st_size // 1024} KB)")
    ps1_content = PS1_SOURCE.read_text(encoding="utf-8")

    # Escape the PS1 content for safe embedding in a Python string
    # We use base64 to avoid any escaping issues
    import base64
    ps1_b64 = base64.b64encode(ps1_content.encode("utf-8")).decode("ascii")

    stub_code = textwrap.dedent(f'''
        """RAIN Enterprise Installer — embedded launcher stub."""
        import os
        import sys
        import base64
        import tempfile
        import subprocess
        import ctypes

        # Embedded PowerShell installer (base64)
        _PS1_B64 = """{ps1_b64}"""

        def is_admin():
            try:
                return ctypes.windll.shell32.IsUserAnAdmin()
            except Exception:
                return False

        def re_elevate():
            """Re-launch self as Administrator via UAC prompt."""
            exe = sys.executable if getattr(sys, "frozen", False) else sys.argv[0]
            params = " ".join(f\'"{a}"\' for a in sys.argv[1:])
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", exe, params, None, 1
            )
            sys.exit(0)

        def main():
            # Request elevation if not already admin
            if not is_admin():
                print("[RAIN] Requesting administrator privileges...")
                re_elevate()

            # Extract the embedded PS1 to a temp file
            ps1_bytes = base64.b64decode(_PS1_B64)
            with tempfile.NamedTemporaryFile(
                suffix="_RAIN-Enterprise-Setup.ps1",
                delete=False,
                mode="wb"
            ) as f:
                f.write(ps1_bytes)
                ps1_path = f.name

            try:
                print(f"[RAIN] Launching installer...")
                result = subprocess.run(
                    [
                        "powershell.exe",
                        "-ExecutionPolicy", "Bypass",
                        "-NoProfile",
                        "-NonInteractive",
                        "-File", ps1_path,
                    ],
                    # Run in the directory the .exe was launched from
                    cwd=os.path.dirname(sys.executable) if getattr(sys, "frozen", False)
                        else os.getcwd(),
                )
                sys.exit(result.returncode)
            finally:
                try:
                    os.unlink(ps1_path)
                except Exception:
                    pass

        if __name__ == "__main__":
            main()
    ''')

    STUB_PY.write_text(stub_code, encoding="utf-8")
    print(f"[INFO] Stub launcher written: {STUB_PY}")

    # Build the PyInstaller command
    icon_arg = ["--icon", str(ICON_FILE)] if ICON_FILE.exists() else []

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--console",                       # shows the terminal (PS window visible)
        "--name",    "RAIN-Enterprise-Setup",
        "--distpath", str(DIST_DIR),
        "--workpath", str(BUILD_DIR / "build_tmp"),
        "--specpath", str(BUILD_DIR),
        "--clean",
        # Windows version info
        "--version-file", str(_write_version_file(BUILD_DIR)),
        *icon_arg,
        str(STUB_PY),
    ]

    print(f"[INFO] Running PyInstaller...")
    print(f"       {' '.join(cmd)}")
    print()

    result = subprocess.run(cmd, cwd=str(REPO_ROOT))

    if result.returncode == 0:
        exe = DIST_DIR / "RAIN-Enterprise-Setup.exe"
        if exe.exists():
            size_mb = exe.stat().st_size / (1024 * 1024)
            print()
            print(f"  ✓ Built successfully!")
            print(f"  Output: {exe}  ({size_mb:.1f} MB)")
            print()
            print("  Distribute RAIN-Enterprise-Setup.exe as a single file.")
            print("  Recipients double-click it — everything is self-contained.")
        else:
            print("[WARN] PyInstaller succeeded but .exe not found at expected path.")
    else:
        print(f"[FAIL] PyInstaller exited with code {result.returncode}")
        sys.exit(result.returncode)

    # Cleanup stub
    STUB_PY.unlink(missing_ok=True)


def _write_version_file(build_dir: Path) -> Path:
    """Write a Windows version resource file for PyInstaller."""
    ver_path = build_dir / "version_info.txt"
    ver_path.write_text(textwrap.dedent("""
        VSVersionInfo(
          ffi=FixedFileInfo(
            filevers=(6,0,0,0),
            prodvers=(6,0,0,0),
            mask=0x3f,
            flags=0x0,
            OS=0x40004,
            fileType=0x1,
            subtype=0x0,
            date=(0, 0)
          ),
          kids=[
            StringFileInfo([
              StringTable(
                u'040904B0',
                [StringStruct(u'CompanyName',      u'ARCOVEL Technologies International'),
                 StringStruct(u'FileDescription',  u'R∞N AI Mastering Engine v6.0 — Enterprise Installer'),
                 StringStruct(u'FileVersion',      u'6.0.0.0'),
                 StringStruct(u'InternalName',     u'RAIN-Enterprise-Setup'),
                 StringStruct(u'LegalCopyright',   u'© 2026 ARCOVEL Technologies International'),
                 StringStruct(u'OriginalFilename', u'RAIN-Enterprise-Setup.exe'),
                 StringStruct(u'ProductName',      u'RAIN AI Mastering Engine'),
                 StringStruct(u'ProductVersion',   u'6.0.0.0')])
            ]),
            VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
          ]
        )
    """), encoding="utf-8")
    return ver_path


if __name__ == "__main__":
    main()
