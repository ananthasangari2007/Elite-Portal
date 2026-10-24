"""
ASGI Entrypoint for Elite Portal FastAPI Application.
Run with:
    uvicorn main:app --host 0.0.0.0 --port 5000 --reload
"""
from app.fastapi.app import create_app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    import os

    port = int(os.getenv("PORT", 5000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
