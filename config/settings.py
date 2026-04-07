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

    # ── DB 전환 스위치 ────────────────────────────────────
    #   "mssql"      → pyodbc   (SQL Server)
    #   "postgresql" → psycopg2 (PostgreSQL)
    DB_MODE: Literal["mssql", "postgresql"] = "mssql"

    # ── SQL Server ────────────────────────────────────────
    MSSQL_SERVER:   str = "localhost"
    MSSQL_PORT:     int = 1433
    MSSQL_DATABASE: str = "mydb"
    MSSQL_USERNAME: str = "sa"
    MSSQL_PASSWORD: str = ""
    MSSQL_DRIVER:   str = "ODBC Driver 17 for SQL Server"

    # ── PostgreSQL ────────────────────────────────────────
    PG_HOST:     str = "localhost"
    PG_PORT:     int = 5432
    PG_DATABASE: str = "mydb"
    PG_USER:     str = "postgres"
    PG_PASSWORD: str = ""

    # ── LLM ──────────────────────────────────────────────
    OLLAMA_BASE_URL:   str = Field(
        default="http://localhost:11434",
        description="Ollama 로컬 서버 (GLM, Gemma3, Qwen)",
    )

    class Config:
        env_file = "config/.env"
        extra    = "ignore"


settings = Settings()
