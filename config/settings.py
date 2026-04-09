"""
config/settings.py
==================
전체 앱 설정의 단일 진실 공급원 (Single Source of Truth).
다른 모듈은 반드시 이 파일에서만 설정값을 가져옵니다.
"""
from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):

    # ── 앱 기본 ──────────────────────────────────────────
    APP_ENV:  Literal["development", "production"] = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    # ── LLM ──────────────────────────────────────────────
    OLLAMA_BASE_URL:   str = Field(
        default="http://localhost:11434",
        description="Ollama 로컬 서버 (GLM, Gemma3, Qwen)",
    )
    OLLAMA_TIMEOUT_SECONDS: float = Field(
        default=180.0,
        description="Ollama 요청 타임아웃(초)",
    )
    OLLAMA_KEEP_ALIVE: str = Field(
        default="10m",
        description='Ollama keep_alive 값 (예: "10m")',
    )

    class Config:
        env_file = "config/.env"
        extra    = "ignore"


settings = Settings()
