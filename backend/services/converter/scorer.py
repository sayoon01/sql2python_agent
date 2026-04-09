"""
backend/services/converter/scorer.py
======================================
변환된 Python 코드 품질 자동 채점기.
정규식 + 휴리스틱 기반. LLM 호출 없음 → 빠르고 결정적.

채점 기준:
  correctness    /25  함수 정의·import·cursor.execute 존재
  type_hints     /20  타입 힌트 (→, : int 등)
  sql_safety     /20  바인딩 파라미터 사용 (f-string 금지)
  error_handling /20  try/except + rollback
  readability    /15  docstring·주석·줄 길이
  ─────────────────────
  total          /100
"""
import ast
import re

from backend.schemas.compare import ScoreDetail


def _has_ast_imports(tree: ast.AST) -> bool:
    return any(isinstance(node, (ast.Import, ast.ImportFrom)) for node in ast.walk(tree))


def _has_ast_function(tree: ast.AST) -> bool:
    return any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) for node in ast.walk(tree))


def _detect_tsql_residue(code: str) -> list[str]:
    findings: list[str] = []
    residue_patterns = [
        (r"\bBEGIN\s+TRY\b", "T-SQL BEGIN TRY 잔재"),
        (r"\bBEGIN\s+CATCH\b", "T-SQL BEGIN CATCH 잔재"),
        (r"\bBEGIN\s+TRAN\b", "T-SQL 트랜잭션 구문 잔재"),
        (r"@@ERROR", "T-SQL @@ERROR 사용"),
        (r"@@ROWCOUNT", "T-SQL @@ROWCOUNT 사용"),
        (r"\bSET\s+@\w+", "T-SQL 변수 대입 잔재"),
        (r"\bPRINT\s+'", "T-SQL PRINT 잔재"),
        (r"ERROR_LINE\(\)", "SQL Server 오류 함수 잔재"),
        (r"ERROR_MESSAGE\(\)", "SQL Server 오류 함수 잔재"),
    ]
    for pattern, label in residue_patterns:
        if re.search(pattern, code, re.IGNORECASE):
            findings.append(label)
    return findings


def _detect_unrealistic_db_patterns(code: str) -> list[str]:
    findings: list[str] = []
    patterns = [
        (r"cursor\.execute\(\s*[\"']BEGIN\s+TRAN", "DB 드라이버에서 직접 BEGIN TRAN 실행"),
        (
            r"cursor\.connection\.getinfo\(pyodbc\.SQL_DIAG_SQLSTATE\)",
            "pyodbc 상태코드로 SQL 성공 여부 판정",
        ),
        (
            r"cursor\.execute\(\s*[\"']SELECT\s+ERROR_LINE\(\)",
            "예외 처리 중 SQL Server 오류 함수 직접 호출",
        ),
    ]
    for pattern, label in patterns:
        if re.search(pattern, code, re.IGNORECASE):
            findings.append(label)
    return findings


def score_code(model_id: str, code: str) -> ScoreDetail:
    """Python 코드를 채점하여 ScoreDetail 을 반환합니다."""

    if not code or len(code.strip()) < 10:
        return ScoreDetail(
            correctness=0, type_hints=0, sql_safety=0,
            error_handling=0, readability=0, total=0,
            strengths=[], weaknesses=["코드 생성 실패"],
            verdict="변환 실패 (0/100)",
        )

    syntax_error = None
    tree = None
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        syntax_error = f"{exc.msg} (line {exc.lineno})"

    # ── 1. 문법 정확성 (25점) ─────────────────────────────
    if tree is not None:
        c = 10  # 문법 유효성
        if _has_ast_function(tree):                           c += 7
        if _has_ast_imports(tree):                            c += 4
        if re.search(r"cursor\.execute\s*\(", code):         c += 2
        if re.search(r"conn\.(cursor|commit|rollback)", code): c += 2
        correctness = min(c, 25)
    else:
        c = 0
        if re.search(r"^def \w+\s*\(", code, re.MULTILINE):     c += 2
        if re.search(r"^(from|import) ", code, re.MULTILINE):   c += 2
        if re.search(r"(cursor\.execute|conn\.)", code):        c += 1
        correctness = min(c, 5)

    # ── 2. 타입 힌트 (20점) ──────────────────────────────
    t = 0
    if re.search(r"->\s*(Optional|List|Dict|int|str|float|None|bool)", code): t += 10
    if re.search(r":\s*(int|str|float|bool|Optional|List|Dict|Any)", code):   t += 10
    type_hints = min(t, 20)

    # ── 3. SQL 안전성 (20점) ─────────────────────────────
    s = 20
    if re.search(r'f["\'].*?(SELECT|INSERT|UPDATE|DELETE)', code, re.IGNORECASE): s -= 15  # f-string SQL
    if re.search(r'\.format\s*\(', code):                                          s -= 8   # str.format
    if re.search(r'cursor\.execute\(sql,\s*[\(\[]', code):                         s += 3   # 바인딩 확인
    sql_safety = max(min(s, 20), 0)

    # ── 4. 예외 처리 (20점) ──────────────────────────────
    e = 0
    if re.search(r"\btry\s*:", code):                e += 7
    if re.search(r"\bexcept\s+Exception", code):     e += 6
    if re.search(r"conn\.rollback\s*\(\)", code):    e += 7
    error_handling = min(e, 20)

    # ── 5. 가독성 (15점) ─────────────────────────────────
    r = 0
    if re.search(r'"""', code):                             r += 6   # docstring
    if re.search(r"#\s+\w", code):                          r += 4   # 주석
    lines = [l for l in code.splitlines() if l.strip()]
    avg_len = sum(len(l) for l in lines) / max(len(lines), 1)
    if avg_len < 80:                                        r += 5   # 줄 길이
    readability = min(r, 15)

    tsql_residue = _detect_tsql_residue(code)
    unrealistic_db_patterns = _detect_unrealistic_db_patterns(code)
    structural_penalty = min(
        len(tsql_residue) * 8 + len(unrealistic_db_patterns) * 6,
        40,
    )

    total = correctness + type_hints + sql_safety + error_handling + readability
    total = max(total - structural_penalty, 0)
    if syntax_error:
        total = min(total, 39)

    # ── 강점 / 약점 ────────────────────────────────────────
    strengths, weaknesses = [], []

    if syntax_error:
        weaknesses.append(f"Python 문법 오류: {syntax_error}")

    if tsql_residue:
        weaknesses.append("T-SQL 구문 잔재")

    if unrealistic_db_patterns:
        weaknesses.append("비현실적 DB 처리 패턴")

    if type_hints >= 15:      strengths.append("타입 힌트 완성")
    else:                     weaknesses.append("타입 힌트 부족")

    if sql_safety >= 18:      strengths.append("SQL 인젝션 안전")
    else:                     weaknesses.append("SQL 안전성 위험")

    if error_handling >= 15:  strengths.append("예외 처리 체계적")
    else:                     weaknesses.append("예외/롤백 미흡")

    if readability >= 12:     strengths.append("가독성 우수")
    else:                     weaknesses.append("문서화 부족")

    if correctness >= 20 and not syntax_error:
        strengths.append("기본 구조 정확")

    grade = (
        "우수" if total >= 80 else
        "양호" if total >= 60 else
        "보통" if total >= 40 else
        "미흡"
    )
    first_point = strengths[0] if strengths else weaknesses[0] if weaknesses else ""
    verdict = f"{grade} ({total}/100) — {first_point}"

    return ScoreDetail(
        correctness=correctness,
        type_hints=type_hints,
        sql_safety=sql_safety,
        error_handling=error_handling,
        readability=readability,
        total=total,
        strengths=strengths,
        weaknesses=weaknesses,
        verdict=verdict,
    )
