"""Backend dev server launcher — loads project root .env, sets backend as CWD."""
import os
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent
project_root = backend_dir.parent

os.chdir(str(backend_dir))
sys.path.insert(0, str(backend_dir))

# Load .env from project root before importing app (dotenv optional)
try:
    from dotenv import load_dotenv
    load_dotenv(project_root / ".env", override=True)
except ImportError:
    pass  # dotenv not installed, use env vars directly

import uvicorn
uvicorn.run(
    "app.main:app",
    host="0.0.0.0",
    port=8000,
    reload=True,
)
