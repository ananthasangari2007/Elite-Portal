"""Backwards-compatible entrypoint (``python run.py`` / ``uvicorn run:app``). Prefer ``main:app``."""
from main import app  # noqa: F401

if __name__ == "__main__":
    import os

    import uvicorn

    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "5000")),
        reload=os.getenv("APP_RELOAD", "false").lower() in {"1", "true", "yes"},
    )
