"""
backend/api/routes/convert.py
==============================
단일 변환 엔드포인트.

POST /api/convert
"""
from fastapi import APIRouter, HTTPException

from backend.schemas.convert import ConvertRequest, ConvertResponse
from backend.services.converter.single import convert_single

router = APIRouter(prefix="/api", tags=["convert"])


@router.post("/convert", response_model=ConvertResponse)
async def convert(req: ConvertRequest) -> ConvertResponse:
    """
    MS SQL 저장 프로시저 → Python 코드 변환 (단일 모델).

    - **model_id**: `glm-4.7-flash-q4km` | `gemma3-27` | `qwen2.5coder-32b`
    - **include_tests**: pytest 코드 포함
    - **include_fastapi_router**: FastAPI 라우터 포함
    """
    result = await convert_single(req)
    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)
    return result
