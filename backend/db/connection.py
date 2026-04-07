"""
backend/db/connection.py
=========================
DB 연결 추상화 레이어.

DB_MODE=mssql      → pyodbc   (SQL Server)
DB_MODE=postgresql → psycopg2 (PostgreSQL)

코드 변경 없이 config/.env 의 DB_MODE 한 줄만 바꾸면 전환됩니다.
"""
from contextlib import contextmanager
from typing import Generator

from config.settings import settings
from backend.core.exceptions import DBError
from backend.core.logging import get_logger

log = get_logger(__name__)


# ── 연결 문자열 빌더 ─────────────────────────────────────────

def _mssql_conn_str() -> str:
    s = settings
    return (
        f"DRIVER={{{s.MSSQL_DRIVER}}};"
        f"SERVER={s.MSSQL_SERVER},{s.MSSQL_PORT};"
        f"DATABASE={s.MSSQL_DATABASE};"
        f"UID={s.MSSQL_USERNAME};"
        f"PWD={s.MSSQL_PASSWORD};"
        "TrustServerCertificate=yes;"
    )


def _pg_kwargs() -> dict:
    s = settings
    return dict(
        host=s.PG_HOST, port=s.PG_PORT,
        dbname=s.PG_DATABASE, user=s.PG_USER, password=s.PG_PASSWORD,
    )


# ── Raw 커넥션 팩토리 ─────────────────────────────────────────

def _open_connection():
    try:
        if settings.DB_MODE == "mssql":
            import pyodbc
            return pyodbc.connect(_mssql_conn_str())
        else:
            import psycopg2
            conn = psycopg2.connect(**_pg_kwargs())
            conn.autocommit = False
            return conn
    except Exception as exc:
        raise DBError(str(exc)) from exc


# ── 컨텍스트 매니저 ───────────────────────────────────────────

@contextmanager
def db_context() -> Generator:
    """
    with db_context() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
    """
    conn = _open_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── FastAPI Depends 용 ────────────────────────────────────────

def get_db_conn():
    """
    @router.get("/items")
    def route(conn=Depends(get_db_conn)): ...
    """
    with db_context() as conn:
        yield conn


# ── 헬퍼 ──────────────────────────────────────────────────────

def get_placeholder() -> str:
    """SQL 파라미터 플레이스홀더: pyodbc=?  psycopg2=%s"""
    return "?" if settings.DB_MODE == "mssql" else "%s"


def ping() -> dict:
    """헬스체크용 연결 확인"""
    try:
        with db_context() as conn:
            conn.cursor().execute("SELECT 1")
        return {"ok": True, "mode": settings.DB_MODE}
    except Exception as exc:
        log.warning("DB ping 실패: %s", exc)
        return {"ok": False, "mode": settings.DB_MODE, "error": str(exc)}
