"""
backend/schemas/convert.py
===========================
단일 변환 요청/응답 Pydantic 스키마.
"""
from typing import Literal, Optional
from pydantic import BaseModel, Field


class ConvertRequest(BaseModel):
    sql_code:              str     = Field(..., min_length=10, description="변환할 MS SQL 프로시저")
    target_db:             Literal["mssql", "postgresql"] = Field("mssql")
    model_id:              str     = Field("glm-4.7-flash-q4km")
    include_tests:         bool    = Field(False, description="pytest 테스트 코드 포함")
    include_fastapi_router: bool   = Field(False, description="FastAPI 라우터 코드 포함")


class ConvertResponse(BaseModel):
    success:        bool
    procedure_name: str
    target_db:      str
    model_id:       str
    python_code:    str
    test_code:      Optional[str] = None
    router_code:    Optional[str] = None
    line_count:     int
    tokens:         Optional[int] = None
    elapsed_ms:     Optional[int] = None
    error:          Optional[str] = None
