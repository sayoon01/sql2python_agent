"""
backend/api/routes/compare.py
==============================
다중 모델 비교 엔드포인트.

POST /api/compare
"""
from fastapi import APIRouter

from backend.schemas.compare import CompareRequest, CompareResponse
from backend.services.converter.compare import compare_models

router = APIRouter(prefix="/api", tags=["compare"])


@router.post("/compare", response_model=CompareResponse)
async def compare(req: CompareRequest) -> CompareResponse:
    """
    동일한 SQL 프로시저를 여러 모델로 동시 변환 후 품질 비교.

    - **model_ids**: 비교할 모델 ID 목록 (2개 이상)
    """
    return await compare_models(req)
