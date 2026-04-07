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
    sections: dict[str, str | None] = {"main": raw.strip(), "test": None, "router": None}

    # 모델별 출력 편차(대괄호/공백/대소문자/접미어)를 흡수하기 위해
    # 헤더를 느슨하게 인식한 뒤 위치 기반으로 섹션을 자릅니다.
    header_pattern = re.compile(
        r"(?im)^\s*\[?\s*(MAIN\s*CODE|TEST\s*CODE|PYTEST\s*CODE|FASTAPI\s*ROUTER(?:\s*CODE)?|SELF\s*CHECK)\s*\]?\s*:?\s*$"
    )

    matches = list(header_pattern.finditer(raw))
    if not matches:
        return sections

    # 헤더명 정규화
    def _key(name: str) -> str:
        n = re.sub(r"\s+", " ", name.strip().upper())
        if n == "MAIN CODE":
            return "main"
        if n in {"TEST CODE", "PYTEST CODE"}:
            return "test"
        if n.startswith("FASTAPI ROUTER"):
            return "router"
        return "other"

    # 헤더 구간별 본문 추출
    extracted: dict[str, str] = {}
    for idx, m in enumerate(matches):
        start = m.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(raw)
        key = _key(m.group(1))
        chunk = raw[start:end].strip()
        # 모델이 넣는 수평 구분선 제거
        chunk = re.sub(r"(?m)^\s*---\s*$", "", chunk).strip()
        if key in {"main", "test", "router"} and chunk:
            extracted[key] = chunk

    # MAIN CODE 헤더가 없더라도 TEST/ROUTER 앞부분을 main으로 사용
    first_start = matches[0].start()
    leading = raw[:first_start].strip()
    leading = re.sub(r"(?m)^\s*---\s*$", "", leading).strip()

    if "main" in extracted:
        sections["main"] = extracted["main"]
    elif leading:
        sections["main"] = leading

    sections["test"] = extracted.get("test")
    sections["router"] = extracted.get("router")
    return sections
