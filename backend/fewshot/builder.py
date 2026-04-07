"""
backend/fewshot/builder.py
===========================
프롬프트 조립기.

역할:
  - fewshot/examples.py 의 데이터를 읽어서
  - target_db / 옵션에 맞는 system prompt 를 조립합니다.

규칙:
  - 이 파일은 문자열 조립만 합니다.
  - LLM 호출, DB 연결, 스키마 등을 import 하지 않습니다.
"""
from backend.fewshot.examples import ALL_EXAMPLES, FewShotExample


# ── DB별 드라이버 정보 ────────────────────────────────────

_DB_META = {
    "mssql": {
        "name": "SQL Server",
        "driver": "pyodbc",
        "conn_type": "pyodbc.Connection",
        "placeholder": "?",
        "scope_identity": "SELECT CAST(SCOPE_IDENTITY() AS INT) AS NewID;",
        "import": "import pyodbc",
        "naming": "테이블/컬럼명 원본 유지",
    },
    "postgresql": {
        "name": "PostgreSQL",
        "driver": "psycopg2",
        "conn_type": "psycopg2.extensions.connection",
        "placeholder": "%s",
        "scope_identity": "RETURNING <컬럼명>  ← PostgreSQL RETURNING 절 사용",
        "import": "import psycopg2\nimport psycopg2.extras",
        "naming": "테이블/컬럼명 snake_case 로 변환",
    },
}


def _format_example(ex: FewShotExample, target_db: str) -> str:
    """FewShotExample 하나를 prompt 텍스트로 변환합니다."""
    python_code = ex.python_pg if target_db == "postgresql" else ex.python_mssql
    return (
        f"### 예시: {ex.title}\n\n"
        f"[SQL 입력]\n{ex.sql}\n\n"
        f"[Python 출력]\n{python_code}"
    )


def build_system_prompt(
    target_db: str,
    include_tests: bool,
    include_router: bool,
) -> str:
    """
    LLM system prompt 를 조립합니다.

    Args:
        target_db: 'mssql' 또는 'postgresql'
        include_tests: pytest 코드 포함 여부
        include_router: FastAPI 라우터 포함 여부

    Returns:
        완성된 system prompt 문자열
    """
    meta = _DB_META.get(target_db, _DB_META["mssql"])
    fewshot_block = "\n\n---\n\n".join(
        _format_example(ex, target_db) for ex in ALL_EXAMPLES
    )

    # 추가 섹션 지시
    extra_sections = ""
    if include_tests:
        extra_sections += (
            "\n\n## 추가 섹션: [TEST CODE]\n"
            "메인 코드 아래 `[TEST CODE]` 헤더 후 pytest + unittest.mock 기반 테스트 코드를 작성하세요.\n"
            "- DB 커넥션은 MagicMock으로 대체합니다.\n"
            "- 정상 케이스 + 예외 케이스를 각각 작성합니다."
        )
    if include_router:
        extra_sections += (
            "\n\n## 추가 섹션: [FASTAPI ROUTER]\n"
            "`[FASTAPI ROUTER]` 헤더 후 FastAPI APIRouter 코드를 작성하세요.\n"
            "- `Depends(get_db_conn)` 패턴으로 DB 주입합니다.\n"
            "- Pydantic 요청/응답 스키마를 함께 정의합니다."
        )

    output_format = "[MAIN CODE]\n(Python 함수 코드)"
    if include_tests:
        output_format += "\n\n[TEST CODE]\n(pytest 코드)"
    if include_router:
        output_format += "\n\n[FASTAPI ROUTER]\n(FastAPI 라우터 코드)"

    return f"""\
당신은 MS SQL Server 저장 프로시저(Stored Procedure)를 실행 가능한 Python 코드로 변환하는 전문가입니다.

## 타겟 환경
- DB: {meta['name']}
- Python 드라이버: {meta['driver']}
- 커넥션 타입 힌트: {meta['conn_type']}
- SQL 파라미터 플레이스홀더: `{meta['placeholder']}`  ← f-string 절대 금지
- SCOPE_IDENTITY 대체: {meta['scope_identity']}
- 네이밍 규칙: {meta['naming']}

## 변환 규칙
1. `@Param` → Python 함수 인자 + 타입 힌트 (int / str / float / bool / Optional[...])
2. `OUTPUT 파라미터` → return value
3. `SET NOCOUNT ON` → 제거
4. `GETDATE()` → `datetime.now()`
5. `BEGIN TRY / CATCH` → `try / except Exception`
6. `BEGIN TRANSACTION / COMMIT / ROLLBACK` → `conn.commit()` / `conn.rollback()`
7. `CURSOR + WHILE` → `fetchall()` 후 `for` 루프 (네트워크 왕복 최소화)
8. 파라미터 바인딩: `{meta['placeholder']}` 플레이스홀더만 사용 (SQL 인젝션 방지)
9. 함수명: ProcedureName → snake_case
10. docstring: 원본 SP 이름 + 주요 변환 규칙 명시
11. 필요한 모든 import 포함{extra_sections}

## 출력 형식
{output_format}

섹션 헤더([MAIN CODE] 등)는 반드시 포함하세요.
마크다운 코드블록(```) 없이 순수 텍스트로 출력하세요.

## Few-shot 변환 예시

{fewshot_block}
"""


def build_user_prompt(sql_code: str) -> str:
    """LLM user prompt 를 조립합니다."""
    return f"다음 MS SQL 프로시저를 변환하세요:\n\n{sql_code}"


def build_eval_prompt(results_summary: str) -> str:
    """비교 평가 종합 코멘트 생성용 프롬프트."""
    return f"""\
아래는 동일한 MS SQL 프로시저를 여러 LLM으로 변환한 결과 요약입니다.
각 모델의 총점, 응답 시간, 강점/약점을 분석하여
2~3문장의 한국어 종합 평가와 실용적 추천을 작성하세요.

{results_summary}

종합 평가:"""
