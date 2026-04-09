"""
backend/services/converter/compare.py
=======================================
다중 모델 병렬 비교 서비스.

흐름:
  CompareRequest
    → 각 model_id 마다 convert_single() 병렬 호출 (asyncio.gather)
    → scorer.py 로 채점
    → GLM(Ollama)로 AI 종합 평가 생성
    → CompareResponse 반환
"""
import asyncio

from backend.schemas.convert import ConvertRequest, ConvertResponse
from backend.schemas.compare import CompareRequest, CompareResponse, CompareResult
from backend.services.converter.single import convert_single
from backend.services.converter.scorer import score_code
from backend.services.converter.parser import extract_procedure_name
from backend.llm.client import get_model_meta, get_adapter
from backend.fewshot.builder import build_eval_prompt
from backend.core.logging import get_logger

log = get_logger(__name__)
SUMMARY_MODEL_ID = "glm-4.7-flash-q4km"


# ── AI 종합 평가 ───────────────────────────────────────────

async def _generate_ai_summary(
    results: list[CompareResult],
    winner: CompareResult,
    failed_models: list[str] | None = None,
) -> str:
    """GLM 이 비교 결과를 분석해 종합 평가 코멘트를 생성합니다."""
    lines = []
    for cr in results:
        label = get_model_meta(cr.convert.model_id).label
        lines.append(
            f"- {label}: 총점 {cr.score.total}/100"
            f", {cr.convert.elapsed_ms or 0}ms"
            f", {cr.convert.line_count}줄"
            f", 강점: {', '.join(cr.score.strengths) or '없음'}"
        )
    if failed_models:
        lines.append(f"- 변환 실패 모델: {', '.join(failed_models)}")
    summary_text = "\n".join(lines)
    winner_label = get_model_meta(winner.convert.model_id).label
    winner_score = winner.score.total
    user_prompt = build_eval_prompt(summary_text, winner_label, winner_score)

    try:
        adapter = get_adapter(SUMMARY_MODEL_ID)
        resp = await adapter.complete(
            system="당신은 모델 비교 평가를 전문적으로 요약하는 한국어 AI 리뷰어입니다.",
            user=user_prompt,
        )
        body = resp.text.strip()
        prefix = f"공식 우승 모델은 {winner_label} ({winner_score}/100)입니다."
        return f"{prefix}\n\n{body}" if body else prefix
    except Exception as exc:
        log.warning("AI 종합 평가 생성 실패: %s", exc)
        # 실패 시 규칙 기반 폴백
        label = winner_label
        failed_note = (
            f" 변환 실패 모델: {', '.join(failed_models)}."
            if failed_models else ""
        )
        return (
            f"{label}가 총점 {winner_score}/100으로 가장 우수한 변환 품질을 보였습니다. "
            f"강점: {', '.join(winner.score.strengths) or '없음'}."
            f"{failed_note}"
        )


# ── 메인 비교 서비스 ───────────────────────────────────────

async def compare_models(req: CompareRequest) -> CompareResponse:
    """여러 모델을 병렬로 호출해 변환 결과를 비교합니다."""
    proc_name = extract_procedure_name(req.sql_code)

    # 1) 병렬 변환 호출
    tasks = [
        convert_single(ConvertRequest(
            sql_code=req.sql_code,
            model_id=mid,
        ))
        for mid in req.model_ids
    ]
    convert_results: list[ConvertResponse] = await asyncio.gather(*tasks)

    # 2) 채점
    compared: list[CompareResult] = [
        CompareResult(
            convert=cr,
            score=score_code(cr.model_id, cr.python_code),
        )
        for cr in convert_results
    ]

    successful = [item for item in compared if item.convert.success]
    failed_models = [item.convert.model_id for item in compared if not item.convert.success]

    if not successful:
        error_message = "모든 모델 변환이 실패했습니다."
        log.warning("비교 실패 — 모델 %d개 모두 변환 실패", len(compared))
        return CompareResponse(
            success=False,
            procedure_name=proc_name,
            results=compared,
            ai_summary=error_message,
            partial_failure=False,
            failed_models=failed_models,
            error=error_message,
        )

    # 3) 우승 모델 결정
    best = max(successful, key=lambda cr: cr.score.total)
    winner_meta = get_model_meta(best.convert.model_id)

    # 4) AI 종합 평가
    ai_summary = await _generate_ai_summary(successful, best, failed_models)
    partial_failure = bool(failed_models)

    log.info(
        "비교 완료 — 성공 %d개, 실패 %d개, 우승: %s (%d점)",
        len(successful), len(failed_models), winner_meta.label, best.score.total,
    )

    return CompareResponse(
        success=True,
        procedure_name=proc_name,
        results=compared,
        winner_model=winner_meta.model_id,
        winner_label=winner_meta.label,
        ai_summary=ai_summary,
        partial_failure=partial_failure,
        failed_models=failed_models,
    )
