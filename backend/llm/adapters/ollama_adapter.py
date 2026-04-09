"""
backend/llm/adapters/ollama_adapter.py
========================================
Ollama 로컬 서버 어댑터.
지원 모델: glm-4.7-flash-q4km (glm-4.7-flash:Q4_K_M), gemma3-27 (gemma3:27b), qwen2.5coder-32b (qwen2.5-coder:32b)

사전 준비:
  ollama pull glm-4.7-flash:Q4_K_M
  ollama pull gemma3:27b
  ollama pull qwen2.5-coder:32b
"""
import time

import httpx

from config.settings import settings
from backend.core.exceptions import LLMError
from backend.llm.adapters.base import BaseLLMAdapter, LLMResponse

# app model_id → ollama 실제 모델명 매핑
_OLLAMA_MODEL_MAP = {
    "glm-4.7-flash-q4km": "glm-4.7-flash:Q4_K_M",
    "gemma3-27":        "gemma3:27b",
    "qwen2.5coder-32b": "qwen2.5-coder:32b",
}


def _format_exception_detail(exc: Exception) -> str:
    """로그와 API 응답에 넣을 예외 요약 문자열."""
    exc_type = type(exc).__name__
    message = str(exc).strip()
    return f"{exc_type}: {message}" if message else exc_type


class OllamaAdapter(BaseLLMAdapter):

    def __init__(self, model_id: str) -> None:
        if model_id not in _OLLAMA_MODEL_MAP:
            raise LLMError(model_id, f"지원하지 않는 Ollama 모델: {model_id}")
        self._model_id   = model_id
        self._ollama_name = _OLLAMA_MODEL_MAP[model_id]
        self._base_url   = settings.OLLAMA_BASE_URL

    async def complete(self, system: str, user: str) -> LLMResponse:
        t0 = time.monotonic()
        payload = {
            "model": self._ollama_name,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
            "stream": False,
            "keep_alive": settings.OLLAMA_KEEP_ALIVE,
        }
        try:
            async with httpx.AsyncClient(timeout=settings.OLLAMA_TIMEOUT_SECONDS) as client:
                resp = await client.post(
                    f"{self._base_url}/api/chat",
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.ConnectError:
            raise LLMError(
                self._model_id,
                f"Ollama 서버에 연결할 수 없습니다 ({self._base_url}). "
                "'ollama serve' 가 실행 중인지 확인하세요.",
            )
        except httpx.TimeoutException as exc:
            raise LLMError(
                self._model_id,
                f"{type(exc).__name__}: {settings.OLLAMA_TIMEOUT_SECONDS}초 내 응답 없음",
            ) from exc
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code if exc.response is not None else "unknown"
            raise LLMError(
                self._model_id,
                f"{type(exc).__name__}: Ollama HTTP {status_code}",
            ) from exc
        except Exception as exc:
            raise LLMError(self._model_id, _format_exception_detail(exc)) from exc

        text   = data["message"]["content"]
        tokens = data.get("eval_count", 0) + data.get("prompt_eval_count", 0)

        return LLMResponse(
            text=text,
            tokens=tokens,
            elapsed_ms=int((time.monotonic() - t0) * 1000),
        )
