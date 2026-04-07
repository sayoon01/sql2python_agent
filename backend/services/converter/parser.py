"""
backend/services/converter/parser.py
======================================
SQL 파싱 + LLM 출력 파싱 유틸.
순수 함수만 포함합니다. 외부 의존성 없음.
"""
import re


# ── SQL 파싱 ──────────────────────────────────────────────

def extract_procedure_name(sql: str) -> str:
    """CREATE PROCEDURE 문에서 프로시저 이름을 추출합니다."""
    pattern = re.compile(
        r"CREATE\s+(?:OR\s+ALTER\s+)?PROCEDURE\s+"   # 헤더
        r"(?:\[?[\w]+\]?\.)?"                          # 스키마 (선택)
        r"\[?(\w+)\]?",                                # 이름
        re.IGNORECASE,
    )
    m = pattern.search(sql)
    return m.group(1) if m else "unknown_procedure"


# ── LLM 출력 파싱 ─────────────────────────────────────────

def strip_markdown_fences(text: str) -> str:
    """마크다운 코드블록(```) 제거."""
    return re.sub(r"^```[\w]*\n?", "", text, flags=re.MULTILINE).replace("```", "").strip()


def split_sections(raw: str) -> dict[str, str | None]:
    """
    LLM 출력을 [MAIN CODE] / [TEST CODE] / [FASTAPI ROUTER] 로 분리합니다.
    섹션 헤더가 없으면 전체를 MAIN CODE로 취급합니다.
    """
    sections: dict[str, str | None] = {
        "main":   raw.strip(),
        "test":   None,
        "router": None,
    }

    if "[MAIN CODE]" in raw:
        m = re.search(
            r"\[MAIN CODE\](.*?)(?=\[TEST CODE\]|\[FASTAPI ROUTER\]|$)",
            raw, re.DOTALL,
        )
        if m:
            sections["main"] = m.group(1).strip()

    m = re.search(r"\[TEST CODE\](.*?)(?=\[FASTAPI ROUTER\]|$)", raw, re.DOTALL)
    if m:
        sections["test"] = m.group(1).strip()

    m = re.search(r"\[FASTAPI ROUTER\](.*?)$", raw, re.DOTALL)
    if m:
        sections["router"] = m.group(1).strip()

    return sections
