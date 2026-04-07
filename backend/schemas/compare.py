"""
backend/schemas/compare.py
===========================
다중 모델 비교 요청/응답 Pydantic 스키마.
"""
from typing import Literal, List, Optional
from pydantic import BaseModel, Field

from backend.schemas.convert import ConvertResponse


class CompareRequest(BaseModel):
    sql_code:  str  = Field(..., min_length=10)
    target_db: Literal["mssql", "postgresql"] = Field("mssql")
    model_ids: List[str] = Field(
        default=[
            "glm-4.7-flash-q4km",
            "gemma3-27",
            "qwen2.5coder-32b",
        ],
        min_length=2,
        description="비교할 모델 ID 목록 (2개 이상)",
    )


class ScoreDetail(BaseModel):
    """채점 항목별 점수."""
    correctness:     int   # /25 — 함수 구조·import·실행 가능성
    type_hints:      int   # /20 — 타입 힌트 완성도
    sql_safety:      int   # /20 — 바인딩 파라미터 사용(인젝션 방지)
    error_handling:  int   # /20 — try/except + rollback
    readability:     int   # /15 — docstring·주석·줄길이
    total:           int   # /100
    strengths:       List[str]
    weaknesses:      List[str]
    verdict:         str   # 한줄 평가


class CompareResult(BaseModel):
    """모델 한 개의 변환 결과 + 점수."""
    convert:  ConvertResponse
    score:    ScoreDetail


class CompareResponse(BaseModel):
    success:        bool
    procedure_name: str
    results:        List[CompareResult]
    winner_model:   str          # 총점 1위 model_id
    winner_label:   str          # 총점 1위 표시명
    ai_summary:     Optional[str] = None
