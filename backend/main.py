"""
backend/main.py
================
FastAPI 애플리케이션 진입점.

역할:
  - FastAPI 인스턴스 생성
  - 미들웨어 등록 (CORS)
  - 라우터 등록
  - 프론트엔드 정적 파일 서빙
  - 예외 핸들러 등록
"""
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.core.exceptions import AppError
from backend.core.logging import setup_logging, get_logger
from backend.api.routes import convert, compare, health

# ── 로깅 초기화 ───────────────────────────────────────────
setup_logging("INFO")
log = get_logger(__name__)

# ── FastAPI 앱 ────────────────────────────────────────────
app = FastAPI(
    title="SQL2Python Agent",
    description="MS SQL 프로시저 → Python 코드 변환 API",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ─────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 라우터 등록 ───────────────────────────────────────────
app.include_router(health.router)
app.include_router(convert.router)
app.include_router(compare.router)

# ── 전역 예외 핸들러 ──────────────────────────────────────
@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"error": exc.code, "message": exc.message},
    )

# ── 프론트엔드 서빙 ───────────────────────────────────────
_FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")

if os.path.isdir(_FRONTEND_DIR):
    # /static → CSS, JS 파일
    _STATIC_DIR = os.path.join(_FRONTEND_DIR, "static")
    if os.path.isdir(_STATIC_DIR):
        app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

        _FAVICON = os.path.join(_STATIC_DIR, "favicon.ico")
        if os.path.isfile(_FAVICON):

            @app.get("/favicon.ico", include_in_schema=False)
            def serve_favicon() -> FileResponse:
                return FileResponse(_FAVICON, media_type="image/x-icon")

    # / → index.html
    @app.get("/", include_in_schema=False)
    def serve_index() -> FileResponse:
        return FileResponse(os.path.join(_FRONTEND_DIR, "index.html"))
