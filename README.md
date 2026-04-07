# SQL2Python Agent v2

MS SQL Server 저장 프로시저(Stored Procedure)를 Python 코드로 변환하는 FastAPI 기반 멀티모델 AI 에이전트.

---

## 아키텍처

```
sql2python/
│
├── config/                              ← ❶ 설정 레이어
│   ├── settings.py                      │   전체 환경변수 단일 관리 (Single Source of Truth)
│   └── .env.example                     │   환경변수 템플릿
│
├── backend/                             ← ❷ 백엔드 레이어
│   │
│   ├── main.py                          │   FastAPI 앱 생성 · 라우터 등록 · 정적파일 서빙
│   │
│   ├── core/                            ← ❷-1 공통 유틸
│   │   ├── exceptions.py                │   AppError / LLMError / DBError / ConvertError
│   │   └── logging.py                   │   get_logger() 공장 함수
│   │
│   ├── db/                              ← ❷-2 DB 레이어
│   │   └── connection.py                │   mssql ↔ postgresql 전환 (DB_MODE 하나로)
│   │                                    │   db_context(), get_db_conn(), ping()
│   │
│   ├── llm/                             ← ❷-3 LLM 레이어
│   │   ├── client.py                    │   MODEL_REGISTRY + get_adapter() 팩토리
│   │   └── adapters/
│   │       ├── base.py                  │   BaseLLMAdapter (인터페이스)
│   │       ├── ollama_adapter.py        │   GLM 4.7 Flash / Gemma3-27 / Qwen2.5Coder-32B (로컬)
│   │
│   │
│   ├── fewshot/                         ← ❷-4 퓨샷 레이어
│   │   ├── examples.yaml                │   SQL→Python 변환 예시 데이터 (순수 데이터)
│   │   └── builder.py                   │   시스템 프롬프트 조립 (순수 문자열)
│   │
│   ├── schemas/                         ← ❷-5 Pydantic 스키마
│   │   ├── convert.py                   │   ConvertRequest / ConvertResponse
│   │   └── compare.py                   │   CompareRequest / CompareResponse / ScoreDetail
│   │
│   ├── services/converter/              ← ❷-6 비즈니스 로직
│   │   ├── parser.py                    │   SQL 파싱 · LLM 출력 파싱 (순수 함수)
│   │   ├── scorer.py                    │   코드 품질 자동 채점 (정규식 기반)
│   │   ├── single.py                    │   단일 모델 변환 서비스
│   │   └── compare.py                   │   병렬 다중 모델 비교 서비스
│   │
│   └── api/routes/                      ← ❷-7 API 레이어
│       ├── convert.py                   │   POST /api/convert
│       ├── compare.py                   │   POST /api/compare
│       └── health.py                    │   GET  /api/health · GET /api/models
│
├── frontend/                            ← ❸ 프론트엔드 레이어
│   ├── index.html                       │   시맨틱 HTML (인라인 스타일/스크립트 없음)
│   └── static/
│       ├── css/style.css                │   화이트 톤 디자인 시스템
│       └── js/app.js                    │   CONFIG · utils · api · singlePage · comparePage
│
├── requirements.txt
└── run.py                               ← 서버 실행 진입점
```

---

## 레이어 책임 요약

| 레이어 | 위치 | 책임 | 외부 의존 |
|--------|------|------|-----------|
| 설정 | `config/` | 환경변수 단일 관리 | pydantic-settings |
| 공통 | `backend/core/` | 예외·로깅 | 없음 |
| DB | `backend/db/` | 연결 전환 (mssql↔pg) | pyodbc, psycopg2 |
| LLM | `backend/llm/` | 모델 호출 추상화 | httpx |
| 퓨샷 | `backend/fewshot/` | 예시 데이터·프롬프트 | PyYAML |
| 스키마 | `backend/schemas/` | 요청/응답 타입 | pydantic |
| 서비스 | `backend/services/` | 변환·채점 로직 | 내부만 |
| API | `backend/api/` | HTTP 라우팅 | FastAPI |
| 프론트 | `frontend/` | UI | 없음 |

---

## 지원 모델

| model_id | 이름 | 공급자 | 연결 |
|----------|------|--------|------|
| `glm-4.7-flash-q4km` | GLM 4.7 Flash (Q4_K_M) | Ollama (로컬) | localhost:11434 |
| `gemma3-27` | Gemma3 27B | Ollama (로컬) | localhost:11434 |
| `qwen2.5coder-32b` | Qwen2.5 Coder 32B | Ollama (로컬) | localhost:11434 |

### Ollama 모델 설치
```bash
ollama pull glm-4.7-flash:Q4_K_M
ollama pull gemma3:27b
ollama pull qwen2.5-coder:32b
```

---

## 빠른 시작

```bash
# 1. 환경 설정
cp config/.env.example config/.env
# → config/.env 편집: DB 정보 및 OLLAMA_BASE_URL 확인/수정

# 2. (권장) 가상환경 생성/활성화
python3 -m venv .venv
source .venv/bin/activate

# 3. 패키지 설치
python -m pip install --upgrade pip
pip install -r requirements.txt

# 4. 실행
python run.py
# 또는 (직접 실행)
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
# → http://localhost:8000 (외부 접근 시 http://<서버IP>:8000)
```

---

## DB 전환 (코드 변경 없음)

`config/.env` 한 줄만 수정:

```env
# SQL Server 사용
DB_MODE=mssql

# PostgreSQL로 전환
DB_MODE=postgresql
```

---

## API 레퍼런스

### POST /api/convert — 단일 변환
```json
{
  "sql_code": "CREATE PROCEDURE ...",
  "target_db": "mssql",
  "model_id": "glm-4.7-flash-q4km",
  "include_tests": false,
  "include_fastapi_router": false
}
```

`include_tests`, `include_fastapi_router` 옵션을 켜면 출력 섹션이 확장됩니다.

- `include_tests=true` → `[TEST CODE]` 섹션 추가 (pytest + unittest.mock)
- `include_fastapi_router=true` → `[FASTAPI ROUTER]` 섹션 추가 (APIRouter + Pydantic)
- 둘 중 하나라도 `true`면 `[SELF CHECK]` 섹션이 함께 생성되어 아래 항목을 PASS/FAIL로 점검합니다.
  - import 누락 없음
  - 테스트 정상/실패/예외 분리
  - commit/rollback 검증
  - execute 호출/인자 검증
  - 라우터 스키마와 반환 구조 일치
  - 라우터 예외의 HTTP 오류 변환
  - 프로젝트 모듈 경로 사용

### POST /api/compare — 모델 비교
```json
{
  "sql_code": "CREATE PROCEDURE ...",
  "target_db": "postgresql",
  "model_ids": ["glm-4.7-flash-q4km", "gemma3-27", "qwen2.5coder-32b"]
}
```

### GET /api/health — 헬스체크
### GET /api/models — 모델 목록
### GET /docs       — Swagger UI

---

## 새 모델 추가 방법

1. `backend/llm/adapters/` 에 어댑터 클래스 작성 (`BaseLLMAdapter` 상속)
2. `backend/llm/client.py` 의 `MODEL_REGISTRY` 에 항목 추가
3. 끝 — 다른 파일 수정 불필요
