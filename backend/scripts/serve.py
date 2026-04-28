"""Entry point: start the FastAPI backend server.

Reload is ON by default for the local development workflow (the
file-watcher cuts ~1.5 s off every code edit). It is OFF when the
process is running under Docker or any other "production-like" mode.

The selector is the ``BACKEND_ENV`` environment variable:
  - unset / "development" / "dev" / "local" -> reload=True
  - anything else (e.g. "production", "docker") -> reload=False

The Dockerfile sets ``BACKEND_ENV=production`` so the container does
not boot with the auto-reload watcher.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uvicorn


def _reload_enabled() -> bool:
    env = os.environ.get("BACKEND_ENV", "development").strip().lower()
    return env in ("", "development", "dev", "local")


if __name__ == "__main__":
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=_reload_enabled(),
    )
