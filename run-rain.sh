#!/bin/bash
# ============================================
# RAIN AI Mastering Engine v6.0 — Local Runner
# ============================================
# Run this file to start RAIN on your machine.
# Opens in your browser at http://localhost:4173
#
# Requirements: Node.js 18+ installed
# ============================================

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIST_DIR="$SCRIPT_DIR/frontend/dist"

if [ ! -d "$DIST_DIR" ]; then
  echo "ERROR: Build not found at $DIST_DIR"
  echo "Run: cd frontend && npm install && npx vite build"
  exit 1
fi

echo ""
echo "  ╔══════════════════════════════════════════╗"
echo "  ║  R∞N AI MASTERING ENGINE v6.0            ║"
echo "  ║  ARCOVEL Technologies International      ║"
echo "  ║                                          ║"
echo "  ║  Rain doesn't live in the cloud.         ║"
echo "  ╚══════════════════════════════════════════╝"
echo ""

# Check if npx is available
if ! command -v npx &> /dev/null; then
  # Fallback: use Python http.server
  if command -v python3 &> /dev/null; then
    echo "  Starting with Python server..."
    echo "  Open: http://localhost:4173"
    echo ""
    cd "$DIST_DIR"
    python3 -m http.server 4173
  else
    echo "ERROR: Neither Node.js nor Python3 found."
    echo "Install Node.js 18+ from https://nodejs.org"
    exit 1
  fi
else
  echo "  Starting RAIN..."
  echo "  Open: http://localhost:4173"
  echo ""
  cd "$SCRIPT_DIR/frontend"
  npx vite preview --host 0.0.0.0 --port 4173
fi
