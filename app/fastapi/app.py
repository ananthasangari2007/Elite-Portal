"""
Elite Portal — FastAPI Application Factory
Francis Xavier Engineering College | Elite Batch 2025-2029
"""
from __future__ import annotations

import logging
import os
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from config import Config
from app.fastapi.database import db, get_db
from app.fastapi.utils import ApiError, fail

# Import routers
from app.fastapi.routers.auth import router as auth_router
from app.fastapi.routers.common import router as common_router
from app.fastapi.routers.student import router as student_router
from app.fastapi.routers.coordinator import router as coordinator_router
from app.fastapi.routers.faculty import router as faculty_router
from app.fastapi.routers.admin import router as admin_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("elite_portal.api")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DIST_DIR = BASE_DIR / "frontend" / "dist"
ASSETS_DIR = DIST_DIR / "assets"
INDEX_HTML = DIST_DIR / "index.html"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup tasks
    logger.info("Starting Elite Portal FastAPI server...")
    try:
        from app.services.elite_sprint import close_expired_sprints
        close_expired_sprints()
    except Exception as e:
        logger.warning(f"Could not run sprint status check on startup: {e}")
    yield
    # Shutdown tasks
    logger.info("Shutting down Elite Portal FastAPI server...")
    db.session.remove()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Elite Portal API",
        description="Francis Xavier Engineering College | Elite Batch 2025-2029 API",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
        dependencies=[Depends(get_db)],
    )

    # ── CORS Middleware ────────────────────────────────────────────────────────
    allowed_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5000",
        "http://127.0.0.1:5000",
    ]
    if os.getenv("FRONTEND_URL"):
        allowed_origins.append(os.getenv("FRONTEND_URL").rstrip("/"))
    if os.getenv("CORS_ORIGINS"):
        for o in os.getenv("CORS_ORIGINS").split(","):
            if o.strip():
                allowed_origins.append(o.strip().rstrip("/"))

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(set(allowed_origins)),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Response-Time"],
    )

    # ── Request Lifecycle & Session Cleanup Middleware ────────────────────────
    @app.middleware("http")
    async def request_lifecycle_middleware(request: Request, call_next):
        req_id = request.headers.get("X-Request-ID") or secrets.token_hex(8)
        start_time = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            try:
                db.session.rollback()
                db.session.remove()
            except Exception:
                pass
            raise
        finally:
            try:
                db.session.remove()
            except Exception:
                pass

        duration_ms = (time.perf_counter() - start_time) * 1000
        response.headers["X-Request-ID"] = req_id
        response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"

        path = request.url.path
        if not path.startswith("/assets/") and not path.endswith((".svg", ".ico", ".png", ".css", ".js", ".map")):
            logger.info(f"[{req_id}] {request.method} {path} -> {response.status_code} ({duration_ms:.1f}ms)")

        return response

    # ── Exception Handlers ────────────────────────────────────────────────────
    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError):
        return JSONResponse(status_code=exc.status_code, content=exc.to_dict())

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException):
        if request.url.path.startswith("/api/"):
            code = "not_found" if exc.status_code == 404 else ("unauthorized" if exc.status_code == 401 else "http_error")
            return JSONResponse(status_code=exc.status_code, content={"error": {"code": code, "message": str(exc.detail)}})
        # For non-API routes, fallback to SPA index.html if file exists
        if exc.status_code == 404 and INDEX_HTML.is_file():
            return FileResponse(INDEX_HTML)
        return JSONResponse(status_code=exc.status_code, content={"error": {"code": "http_error", "message": str(exc.detail)}})

    @app.exception_handler(Exception)
    async def handle_general_exception(request: Request, exc: Exception):
        logger.exception(f"Unhandled exception on {request.method} {request.url.path}")
        try:
            db.session.rollback()
            db.session.remove()
        except Exception:
            pass
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "server_error", "message": "An internal server error occurred."}},
        )

    # ── Health Endpoint ───────────────────────────────────────────────────────
    @app.get("/health", tags=["system"])
    @app.get("/api/v1/health", tags=["system"])
    def health_check():
        db_status = "ok"
        try:
            db.session.execute(text("SELECT 1"))
        except Exception:
            db.session.rollback()
            try:
                db.session.execute(text("SELECT 1"))
            except Exception as e:
                db_status = f"unhealthy: {e.__class__.__name__}"
        return {
            "status": "ok" if db_status == "ok" else "degraded",
            "database": db_status,
            "version": "1.0.0",
            "framework": "FastAPI",
        }

    # ── Register Routers ──────────────────────────────────────────────────────
    app.include_router(auth_router)
    app.include_router(common_router)
    app.include_router(student_router)
    app.include_router(coordinator_router)
    app.include_router(faculty_router)
    app.include_router(admin_router)

    # ── Static Uploads & SPA Assets ───────────────────────────────────────────
    upload_dir = Path(getattr(Config, "UPLOAD_FOLDER", "uploads"))
    upload_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=str(upload_dir)), name="uploads")

    if ASSETS_DIR.is_dir():
        app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")

    if INDEX_HTML.is_file():
        @app.get("/favicon.svg", include_in_schema=False)
        def favicon():
            fav = DIST_DIR / "favicon.svg"
            if fav.is_file():
                return FileResponse(fav)
            return JSONResponse(status_code=404, content={"error": "not found"})

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa_fallback(full_path: str):
            if full_path.startswith("api/"):
                return JSONResponse(status_code=404, content={"error": {"code": "not_found", "message": "API endpoint not found."}})
            potential_file = DIST_DIR / full_path
            if potential_file.is_file():
                return FileResponse(potential_file)
            return FileResponse(INDEX_HTML)

    return app
