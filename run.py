"""
Application entrypoint for Elite Portal.
Now powered by FastAPI / Uvicorn with full backwards compatibility.
"""
import os
import uvicorn
from app.fastapi.app import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    host = os.getenv("HOST", "0.0.0.0")
    reload = os.getenv("APP_RELOAD", "false").lower() in {"1", "true", "yes"}
    uvicorn.run("run:app", host=host, port=port, reload=reload)
