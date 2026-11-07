"""
ASGI entrypoint for the Elite Portal FastAPI application.

Production:   uvicorn main:app --host 0.0.0.0 --port $PORT --proxy-headers
Development:  python main.py   (auto-reload, port 5000)
"""
import os

from app.fastapi.app import create_app

app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "5000")),
        reload=os.getenv("APP_RELOAD", "true").lower() in {"1", "true", "yes"},
    )
