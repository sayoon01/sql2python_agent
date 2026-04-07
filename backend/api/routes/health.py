"""
backend/api/routes/health.py
=============================
헬스체크 엔드포인트.

GET /api/health
GET /api/models
"""
from fastapi import APIRouter

from backend.db.connection import ping
from backend.llm.client import list_models

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
def health() -> dict:
    """앱 + DB 연결 상태 확인."""
    return {
        "app":    "sql2python",
        "status": "ok",
        "db":     ping(),
    }


@router.get("/models")
def models() -> dict:
    """사용 가능한 LLM 모델 목록 반환."""
    return {"models": list_models()}
