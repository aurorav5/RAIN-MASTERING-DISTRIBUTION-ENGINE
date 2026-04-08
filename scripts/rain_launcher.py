"""
RAIN AI Mastering Engine — Desktop Launcher
Starts Docker services and opens the browser to the RAIN UI.
"""
import subprocess
import sys
import os
import time
import webbrowser
import urllib.request
import ctypes

# ─── Config ──────────────────────────────────────────────────────────────────

RAIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_URL = "http://localhost:5173"
BACKEND_HEALTH = "http://localhost:8000/health"
MAX_WAIT = 120  # seconds


def set_title(title: str):
    """Set console window title."""
    if sys.platform == "win32":
        ctypes.windll.kernel32.SetConsoleTitleW(title)


def log(msg: str):
    print(f"  [RAIN] {msg}")


def check_docker():
    """Verify Docker is running."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True, timeout=10
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def check_url(url: str) -> bool:
    """Check if a URL is reachable."""
    try:
        req = urllib.request.urlopen(url, timeout=3)
        return req.status == 200
    except Exception:
        return False


def start_services():
    """Start Docker Compose services."""
    log("Starting RAIN services...")
    subprocess.run(
        ["docker", "compose", "up", "-d"],
        cwd=RAIN_DIR,
        capture_output=True,
    )


def wait_for_health():
    """Wait for backend + frontend to be ready."""
    log("Waiting for services to start...")
    start = time.time()
    backend_ready = False
    frontend_ready = False

    while time.time() - start < MAX_WAIT:
        if not backend_ready and check_url(BACKEND_HEALTH):
            backend_ready = True
            log("✓ Backend ready")

        if not frontend_ready and check_url(FRONTEND_URL):
            frontend_ready = True
            log("✓ Frontend ready")

        if backend_ready and frontend_ready:
            return True

        time.sleep(2)
        elapsed = int(time.time() - start)
        sys.stdout.write(f"\r  [RAIN] Waiting... {elapsed}s")
        sys.stdout.flush()

    print()
    return backend_ready and frontend_ready


def main():
    set_title("R∞N AI Mastering Engine")

    print()
    print("  ╔══════════════════════════════════════════════╗")
    print("  ║   R∞N — RAIN AI Mastering Engine v6.0       ║")
    print("  ║   ARCOVEL Technologies International        ║")
    print("  ╚══════════════════════════════════════════════╝")
    print()

    # Check Docker
    log("Checking Docker...")
    if not check_docker():
        log("ERROR: Docker is not running!")
        log("Please start Docker Desktop and try again.")
        input("\n  Press Enter to exit...")
        sys.exit(1)

    # Check if already running
    if check_url(BACKEND_HEALTH) and check_url(FRONTEND_URL):
        log("RAIN is already running!")
        log(f"Opening {FRONTEND_URL}")
        webbrowser.open(FRONTEND_URL)
        input("\n  Press Enter to exit (services keep running)...")
        return

    # Start services
    start_services()

    # Wait for health
    if wait_for_health():
        print()
        log("══════════════════════════════════════")
        log("  RAIN is ready!")
        log(f"  UI:   {FRONTEND_URL}")
        log(f"  API:  http://localhost:8000/docs")
        log(f"  MinIO: http://localhost:9001")
        log("══════════════════════════════════════")
        print()
        webbrowser.open(FRONTEND_URL)
    else:
        log("WARNING: Services may not be fully ready yet.")
        log(f"Try opening {FRONTEND_URL} manually.")

    input("  Press Enter to exit (services keep running)...")


if __name__ == "__main__":
    main()
