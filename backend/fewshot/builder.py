"""
backend/fewshot/builder.py
===========================
프롬프트 조립기.

역할:
  - fewshot/examples.yaml 의 데이터를 읽어서
  - MSSQL 고정 규칙과 옵션에 맞는 system prompt 를 조립합니다.

규칙:
  - 이 파일은 문자열 조립만 합니다.
  - LLM 호출, DB 연결, 스키마 등을 import 하지 않습니다.
"""
from dataclasses import dataclass
from pathlib import Path

try:
    import yaml
except ModuleNotFoundError as exc:  # pragma: no cover
    raise RuntimeError(
        "PyYAML이 필요합니다. `pip install -r requirements.txt`를 먼저 실행해주세요."
    ) from exc


@dataclass(frozen=True)
class FewShotExample:
    title: str
    sql: str
    python_code: str


def _load_examples() -> list[FewShotExample]:
    data_path = Path(__file__).with_name("examples.yaml")
    raw = yaml.safe_load(data_path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise RuntimeError("examples.yaml 형식 오류: list 여야 합니다.")
    return [FewShotExample(**item) for item in raw]


ALL_EXAMPLES: list[FewShotExample] = _load_examples()


# ── 고정 타겟 환경 정보 ───────────────────────────────────

_DB_META = {
    "name": "SQL Server",
    "driver": "DB-API 2.0 호환 커넥션",
    "conn_type": "conn 객체",
    "placeholder": "?",
    "scope_identity": "SELECT CAST(SCOPE_IDENTITY() AS INT) AS NewID;",
    "import": "필요한 표준 라이브러리만 import",
    "naming": "테이블/컬럼명 원본 유지",
}


def _format_example(ex: FewShotExample) -> str:
    """FewShotExample 하나를 prompt 텍스트로 변환합니다."""
    return (
        f"### 예시: {ex.title}\n\n"
        f"[SQL 입력]\n{ex.sql}\n\n"
        f"[Python 출력]\n{ex.python_code}"
    )


def build_system_prompt(
    include_tests: bool,
    include_router: bool,
) -> str:
    """
    LLM system prompt 를 조립합니다.

    Args:
        include_tests: pytest 코드 포함 여부
        include_router: FastAPI 라우터 포함 여부

    Returns:
        완성된 system prompt 문자열
    """
    meta = _DB_META
    fewshot_block = "\n\n---\n\n".join(
        _format_example(ex) for ex in ALL_EXAMPLES
    )

    # 추가 섹션 지시
    extra_sections = ""
    quality_check_required = include_tests or include_router
    if include_tests:
        extra_sections += (
            "\n\n## 추가 섹션: [TEST CODE]\n"
            "메인 코드 아래 `[TEST CODE]` 헤더 후 pytest + unittest.mock 기반 테스트 코드를 작성하세요.\n"
            "- DB 커넥션은 MagicMock으로 대체합니다.\n"
            "- 정상/실패/예외 케이스를 분리해서 작성합니다.\n"
            "- 각 케이스에서 commit/rollback 호출 여부를 assert 하세요.\n"
            "- 실행 불가 코드가 되지 않도록 import 누락을 금지합니다."
        )
    if include_router:
        extra_sections += (
            "\n\n## 추가 섹션: [FASTAPI ROUTER]\n"
            "`[FASTAPI ROUTER]` 헤더 후 FastAPI APIRouter 코드를 작성하세요.\n"
            "- 엔드포인트 함수는 `conn` 인자를 직접 받는 구조로 작성하세요.\n"
            "- Pydantic 요청/응답 스키마를 함께 정의합니다.\n"
            "- 요청/응답 스키마 키는 메인 함수 반환 구조와 일치해야 합니다."
        )
    if quality_check_required:
        extra_sections += (
            "\n\n## 추가 섹션: [SELF CHECK]\n"
            "아래 항목을 PASS/FAIL 형식으로 자체 점검해 출력하세요.\n"
            "- import 누락 없음\n"
            "- 테스트가 정상/실패/예외 케이스로 분리됨\n"
            "- 테스트에서 commit/rollback 검증 포함\n"
            "- 라우터 스키마와 메인 함수 반환 구조가 일치\n"
            "- 프로젝트 모듈 경로/의존성 사용이 현실적임"
        )

    output_format = "[MAIN CODE]\n(Python 함수 코드)"
    if include_tests:
        output_format += "\n\n[TEST CODE]\n(pytest 코드)"
    if include_router:
        output_format += "\n\n[FASTAPI ROUTER]\n(FastAPI 라우터 코드)"
    if quality_check_required:
        output_format += "\n\n[SELF CHECK]\n(PASS/FAIL 체크리스트)"

    return f"""\
당신은 MS SQL Server 저장 프로시저(Stored Procedure)를 실행 가능한 Python 코드로 변환하는 전문가입니다.

## 타겟 환경
- DB: {meta['name']}
- Python 실행 방식: {meta['driver']}
- 커넥션 입력 형태: {meta['conn_type']}
- SQL 파라미터 플레이스홀더: `{meta['placeholder']}`  ← f-string 절대 금지
- SCOPE_IDENTITY 대체: {meta['scope_identity']}
- 네이밍 규칙: {meta['naming']}

## 변환 규칙
    ### [핵심 원칙]
    1. 변환된 Python 코드는 반드시 실행 가능해야 하며, 원본 SQL 저장 프로시저의 기능, 분기, 성공/실패 조건, 트랜잭션 흐름을 그대로 유지합니다.
    2. 원본 SQL에 없는 로직, 임의 메시지, 임의 조건, 추가 처리 방식은 넣지 않습니다.
    3. 응답은 설명 없이 실행 가능한 Python 함수 코드만 출력합니다.
    4. 필요한 모든 import는 누락 없이 포함합니다.
    5. 존재가 불명확한 프로젝트 내부 모듈은 임의로 import하지 않습니다.
    5-1. 특정 드라이버(`pyodbc`, `pymssql`) import를 강제하지 말고, 전달받은 `conn` 객체의 `cursor/commit/rollback`만 사용합니다.

    ### [함수 및 반환]
    6. 프로시저명은 snake_case 함수명으로 변환합니다.
    7. `@Param`은 Python 함수 인자와 타입 힌트로 변환합니다.
    8. 타입 힌트는 가능한 범위에서 적용하며, nullable인 경우에만 `Optional[...]`을 사용합니다.
    8-1. `conn` 인자는 구체 드라이버 타입 힌트 대신 `Any` 또는 타입 힌트 생략을 사용합니다.
    9. OUTPUT 파라미터는 return value(dict)로 변환합니다.

    ### [DB 실행 규칙]
    10. SQL 실행은 `cursor = conn.cursor()` 후 `cursor.execute()`로 수행합니다.
    11. 파라미터는 문자열 포매팅을 금지하고, DB 드라이버의 placeholder 바인딩만 사용합니다.
    12. `conn`은 autocommit=False로 가정하고, 트랜잭션은 명시적으로 처리합니다.

    ### [SQL → Python 변환]
    13. `SET NOCOUNT ON`, `PRINT`는 제거합니다.
    14. `GETDATE()`는 `datetime.now()`로 변환합니다.
    15. `BEGIN TRY / CATCH`는 `try / except Exception`으로 변환합니다.
    16. `BEGIN TRAN / COMMIT / ROLLBACK`은 `conn.commit()` / `conn.rollback()`으로 변환합니다.
    17. `@@ROWCOUNT`는 `cursor.rowcount`로 변환합니다.

    ### [중요 로직 규칙]
    18. 성공/실패 판단은 반드시 원본 SQL의 조건(`@@ROWCOUNT` 등)을 그대로 따릅니다.
    19. 중간에 return하지 말고, 원본처럼 마지막에 commit/rollback을 결정합니다.
    20. 예외 발생 시 반드시 `conn.rollback()` 후 실패 결과를 반환합니다.


## 출력 형식
{output_format}
{extra_sections}

섹션 헤더([MAIN CODE] 등)는 반드시 포함하세요.
마크다운 코드블록(```) 없이 순수 텍스트로 출력하세요.

## Few-shot 변환 예시

{fewshot_block}
"""


def build_user_prompt(sql_code: str) -> str:
    """LLM user prompt 를 조립합니다."""
    return f"다음 MS SQL 프로시저를 변환하세요:\n\n{sql_code}"


def build_eval_prompt(results_summary: str, winner_label: str, winner_score: int) -> str:
    """비교 평가 종합 코멘트 생성용 프롬프트."""
    return f"""\
아래는 동일한 MS SQL 프로시저를 여러 LLM으로 변환한 결과 요약입니다.
점수 기준 공식 우승 모델은 반드시 {winner_label} ({winner_score}/100) 입니다.
이 사실을 뒤집거나 다른 모델을 1위라고 쓰면 안 됩니다.
각 모델의 총점, 응답 시간, 강점/약점을 분석하여
2~3문장의 한국어 종합 평가와 실용적 추천을 작성하세요.

{results_summary}

종합 평가:"""
