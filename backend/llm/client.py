"""
backend/llm/client.py
======================
LLM 클라이언트 팩토리 & 모델 레지스트리.

새 모델 추가 방법:
  1. backend/llm/adapters/ 에 어댑터 클래스 작성
  2. MODEL_REGISTRY 에 항목 추가
  3. 끝 — 다른 파일 수정 불필요
"""
from dataclasses import dataclass
from typing import Callable

from backend.llm.adapters.base import BaseLLMAdapter


# ── 모델 메타데이터 ────────────────────────────────────────

@dataclass(frozen=True)
class ModelMeta:
    model_id:  str
    label:     str       # UI 표시명
    provider:  str       # ollama
    color:     str       # 16진 색상 (UI 배지용)
    factory:   Callable[[], BaseLLMAdapter]  # 어댑터 생성 함수


# ── 레지스트리 ─────────────────────────────────────────────

def _make_glm():
    from backend.llm.adapters.ollama_adapter import OllamaAdapter
    return OllamaAdapter("glm-4.7-flash-q4km")

def _make_gemma():
    from backend.llm.adapters.ollama_adapter import OllamaAdapter
    return OllamaAdapter("gemma3-27")

def _make_qwen():
    from backend.llm.adapters.ollama_adapter import OllamaAdapter
    return OllamaAdapter("qwen2.5coder-32b")


MODEL_REGISTRY: dict[str, ModelMeta] = {
    "glm-4.7-flash-q4km": ModelMeta(
        model_id="glm-4.7-flash-q4km",
        label="GLM 4.7 Flash (Q4_K_M)",
        provider="ollama",
        color="#C2700A",
        factory=_make_glm,
    ),
    "gemma3-27": ModelMeta(
        model_id="gemma3-27",
        label="Gemma3 27B",
        provider="ollama",
        color="#1D57C4",
        factory=_make_gemma,
    ),
    "qwen2.5coder-32b": ModelMeta(
        model_id="qwen2.5coder-32b",
        label="Qwen2.5 Coder 32B",
        provider="ollama",
        color="#6427C4",
        factory=_make_qwen,
    ),
}

DEFAULT_MODEL_ID = "glm-4.7-flash-q4km"


# ── 팩토리 함수 ────────────────────────────────────────────

def get_adapter(model_id: str) -> BaseLLMAdapter:
    """
    model_id 로 어댑터 인스턴스를 반환합니다.
    미등록 model_id 는 ValueError 를 발생시킵니다.
    """
    meta = MODEL_REGISTRY.get(model_id)
    if meta is None:
        valid = list(MODEL_REGISTRY.keys())
        raise ValueError(f"미등록 모델: '{model_id}'. 사용 가능: {valid}")
    return meta.factory()


def get_model_meta(model_id: str) -> ModelMeta:
    """모델 메타데이터 조회."""
    meta = MODEL_REGISTRY.get(model_id)
    if meta is None:
        raise ValueError(f"미등록 모델: '{model_id}'")
    return meta


def list_models() -> list[dict]:
    """UI 에서 사용할 모델 목록 반환."""
    return [
        {
            "model_id": m.model_id,
            "label":    m.label,
            "provider": m.provider,
            "color":    m.color,
        }
        for m in MODEL_REGISTRY.values()
    ]
