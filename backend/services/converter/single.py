"""
backend/services/converter/single.py
======================================
단일 모델 변환 서비스.

흐름:
  ConvertRequest
    → fewshot/builder.py 로 프롬프트 조립
    → llm/client.py 로 모델 호출
    → parser.py 로 출력 파싱
    → ConvertResponse 반환
"""
from backend.fewshot.builder import build_system_prompt, build_user_prompt
from backend.llm.client import get_adapter
from backend.schemas.convert import ConvertRequest, ConvertResponse
from backend.services.converter.parser import (
    extract_procedure_name,
    strip_markdown_fences,
    split_sections,
)
from backend.core.logging import get_logger

log = get_logger(__name__)


async def convert_single(req: ConvertRequest) -> ConvertResponse:
    """
    단일 모델로 SQL 프로시저를 Python 코드로 변환합니다.
    오류 발생 시에도 ConvertResponse(success=False) 를 반환합니다.
    """
    proc_name = extract_procedure_name(req.sql_code)

    system = build_system_prompt(
        target_db=req.target_db,
        include_tests=req.include_tests,
        include_router=req.include_fastapi_router,
    )
    user = build_user_prompt(req.sql_code)

    try:
        adapter  = get_adapter(req.model_id)
        llm_resp = await adapter.complete(system, user)
    except Exception as exc:
        log.warning("[%s] 변환 실패: %s", req.model_id, exc)
        return ConvertResponse(
            success=False,
            procedure_name=proc_name,
            target_db=req.target_db,
            model_id=req.model_id,
            python_code="",
            line_count=0,
            error=str(exc),
        )

    raw      = strip_markdown_fences(llm_resp.text)
    sections = split_sections(raw)

    log.info("[%s] 완료 — %d tokens, %dms", req.model_id, llm_resp.tokens, llm_resp.elapsed_ms)

    return ConvertResponse(
        success=True,
        procedure_name=proc_name,
        target_db=req.target_db,
        model_id=req.model_id,
        python_code=sections["main"],
        test_code=sections["test"],
        router_code=sections["router"],
        line_count=len(sections["main"].splitlines()),
        tokens=llm_resp.tokens,
        elapsed_ms=llm_resp.elapsed_ms,
    )
