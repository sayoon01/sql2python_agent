"""
backend/llm/adapters/base.py
=============================
모든 LLM 어댑터가 구현해야 하는 인터페이스.
새 모델 추가 시 이 클래스를 상속합니다.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class LLMResponse:
    text:       str
    tokens:     int
    elapsed_ms: int = field(default=0)


class BaseLLMAdapter(ABC):
    """LLM 어댑터 추상 기반 클래스."""

    @abstractmethod
    async def complete(self, system: str, user: str) -> LLMResponse:
        """
        system + user 프롬프트로 텍스트를 생성합니다.

        Returns:
            LLMResponse(text, tokens, elapsed_ms)
        """
        ...
