"""
Elite Portal — FastAPI Application Factory
Francis Xavier Engineering College | Elite Batch 2025-2029
"""
from __future__ import annotations

import logging
import os
import re
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException

from config import Config
from app.fastapi.auth import check_csrf
from app.fastapi.database import db, remove_session, request_scope
from app.fastapi.utils import ApiError

from app.fastapi.routers.auth import router as auth_router
from app.fastapi.routers.common import router as common_router
from app.fastapi.routers.student import router as student_router
from app.fastapi.routers.coordinator import router as coordinator_router
from app.fastapi.routers.faculty import router as faculty_router
from app.fastapi.routers.admin import router as admin_router

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("elite_portal.api")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DIST_DIR = (BASE_DIR / "frontend" / "dist").resolve()
ASSETS_DIR = DIST_DIR / "assets"
INDEX_HTML = DIST_DIR / "index.html"

APP_VERSION = "1.1.0"
MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
REQUEST_ID_RE = re.compile(r"[A-Za-z0-9-]{8,64}")
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


def _allowed_origins() -> list[str]:
    origins = set(getattr(Config, "CORS_ORIGINS", []) or [])
    if os.getenv("FRONTEND_URL"):
        origins.add(os.getenv("FRONTEND_URL").rstrip("/"))
    return sorted(o.rstrip("/") for o in origins if o)


def _database_ok() -> bool:
    try:
        db.session.execute(text("SELECT 1"))
        return True
    except Exception:
        logger.warning("Database readiness check failed", exc_info=True)
        return False
    finally:
        remove_session()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Elite Portal API (production=%s)", Config.is_production)
    from app.services.storage import r2_configured

    if Config.is_production and not r2_configured():
        logger.warning(
            "R2 storage is not configured: uploads are written to local disk (%s), which is not "
            "durable on most hosting platforms. Set R2_ENDPOINT_URL, R2_ACCESS_KEY_ID, "
            "R2_SECRET_ACCESS_KEY and R2_BUCKET_NAME.",
            Config.UPLOAD_FOLDER,
        )
    try:
        from app.services.elite_sprint import close_expired_sprints

        await run_in_threadpool(close_expired_sprints)
    except Exception:
        logger.warning("Sprint status check on startup failed", exc_info=True)
    finally:
        await run_in_threadpool(remove_session)
    yield
    logger.info("Shutting down Elite Portal API")
    await run_in_threadpool(remove_session)
    db.engine.dispose()


def create_app() -> FastAPI:
    docs_enabled = not Config.is_production or os.getenv("ENABLE_API_DOCS", "").lower() in {"1", "true"}
    app = FastAPI(
        title="Elite Portal API",
        description="Francis Xavier Engineering College | Elite Batch 2025-2029 API",
        version=APP_VERSION,
        docs_url="/api/docs" if docs_enabled else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if docs_enabled else None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed_origins(),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-CSRF-Token", "X-Requested-With", "X-Request-ID"],
        expose_headers=["X-Request-ID", "X-Response-Time"],
    )

    @app.middleware("http")
    async def request_lifecycle_middleware(request: Request, call_next):
        supplied_id = request.headers.get("X-Request-ID", "")
        req_id = supplied_id if REQUEST_ID_RE.fullmatch(supplied_id) else secrets.token_hex(8)
        start_time = time.perf_counter()

        # One DB session per request; uncommitted work is rolled back when the request ends.
        scope_token = request_scope.set(f"req-{req_id}-{secrets.token_hex(4)}")
        try:
            csrf_error = None
            if request.method in MUTATING_METHODS and request.url.path.startswith("/api/"):
                csrf_error = check_csrf(request)
            if csrf_error is not None:
                response = JSONResponse(status_code=403, content=csrf_error)
            else:
                response = await call_next(request)
        finally:
            await run_in_threadpool(remove_session)
            request_scope.reset(scope_token)

        duration_ms = (time.perf_counter() - start_time) * 1000
        response.headers["X-Request-ID"] = req_id
        response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"
        for header, value in SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        path = request.url.path
        if path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
            # Path + status + timing only: no query strings, bodies or credentials in logs.
            logger.info("[%s] %s %s -> %s (%.1fms)", req_id, request.method, path, response.status_code, duration_ms)
        return response

    # ── Exception handlers: every API error uses {"error": {"code", "message"}} ──
    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError):
        return JSONResponse(status_code=exc.status_code, content=exc.to_dict())

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        details = [
            {"field": ".".join(str(p) for p in err.get("loc", ())[1:]), "message": err.get("msg", "")}
            for err in exc.errors()
        ]
        first = details[0] if details else {"field": "", "message": "Invalid request."}
        label = f"{first['field']}: " if first["field"] else ""
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "validation_error", "message": f"{label}{first['message']}", "details": details}},
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException):
        codes = {401: "unauthenticated", 403: "forbidden", 404: "not_found", 405: "method_not_allowed"}
        if not request.url.path.startswith("/api/") and exc.status_code == 404 and INDEX_HTML.is_file():
            return FileResponse(INDEX_HTML)
        message = "Resource not found." if exc.status_code == 404 else str(exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": codes.get(exc.status_code, "http_error"), "message": message}},
        )

    @app.exception_handler(Exception)
    async def handle_general_exception(request: Request, exc: Exception):
        logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "server_error", "message": "An internal server error occurred."}},
        )

    # ── Health (liveness) and readiness ───────────────────────────────────────
    @app.get("/health", tags=["system"])
    @app.get("/api/v1/health", tags=["system"])
    def health_check():
        database = "ok" if _database_ok() else "unavailable"
        return {
            "status": "ok" if database == "ok" else "degraded",
            "database": database,
            "version": APP_VERSION,
            "framework": "FastAPI",
        }

    @app.get("/ready", tags=["system"])
    @app.get("/api/v1/ready", tags=["system"])
    def readiness_check():
        if _database_ok():
            return {"status": "ready"}
        return JSONResponse(status_code=503, content={"status": "not_ready"})

    app.include_router(auth_router)
    app.include_router(common_router)
    app.include_router(student_router)
    app.include_router(coordinator_router)
    app.include_router(faculty_router)
    app.include_router(admin_router)

    # Uploaded files are served only through GET /api/v1/files/{key}, which enforces
    # ownership/role checks. (A public /uploads mount previously bypassed those checks.)

    if ASSETS_DIR.is_dir():
        app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")

    if INDEX_HTML.is_file():
        @app.get("/{full_path:path}", include_in_schema=False)
        def spa_fallback(full_path: str):
            if full_path.startswith("api/"):
                return JSONResponse(
                    status_code=404, content={"error": {"code": "not_found", "message": "API endpoint not found."}}
                )
            candidate = (DIST_DIR / full_path).resolve()
            if full_path and DIST_DIR in candidate.parents and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(INDEX_HTML, headers={"Cache-Control": "no-cache"})

    return app
