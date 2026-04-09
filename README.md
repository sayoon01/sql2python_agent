# SQL2Python Agent v2

MS SQL Server 저장 프로시저를 Python 함수 코드로 변환하고, 여러 LLM 결과를 비교 평가하는 FastAPI 기반 프로젝트입니다. 현재 구현은 백엔드 API와 정적 프런트엔드를 하나의 앱에서 함께 서빙하는 구조입니다.

## 1. 프로젝트가 실제로 하는 일

이 프로젝트는 크게 두 가지 기능을 제공합니다.

1. 단일 모델 변환
원본 SQL 프로시저를 받아 선택한 모델 1개로 Python 코드를 생성합니다.

2. 다중 모델 비교
같은 SQL 프로시저를 여러 모델에 동시에 보내고, 생성된 Python 코드에 대해 규칙 기반 점수를 매긴 뒤 우승 모델과 AI 요약을 반환합니다.

핵심 전제는 다음과 같습니다.

- 입력은 MS SQL 저장 프로시저 문자열입니다.
- 출력은 실행 가능한 Python 함수 코드 문자열입니다.
- 실제 SQL 의미 해석과 코드 생성은 Ollama에 연결된 로컬 LLM이 담당합니다.
- 비교 기능의 점수화는 LLM이 아니라 정규식 기반 휴리스틱으로 처리됩니다.

## 2. 현재 구조

```text
sql2python/
├── backend/
│   ├── api/routes/
│   │   ├── health.py
│   │   ├── convert.py
│   │   └── compare.py
│   ├── core/
│   │   ├── exceptions.py
│   │   └── logging.py
│   ├── db/connection.py
│   ├── fewshot/
│   │   ├── builder.py
│   │   └── examples.yaml
│   ├── llm/
│   │   ├── client.py
│   │   └── adapters/
│   │       ├── base.py
│   │       └── ollama_adapter.py
│   ├── schemas/
│   │   ├── convert.py
│   │   └── compare.py
│   ├── services/converter/
│   │   ├── single.py
│   │   ├── compare.py
│   │   ├── parser.py
│   │   └── scorer.py
│   └── main.py
├── config/settings.py
├── frontend/
│   ├── index.html
│   └── static/
│       ├── css/style.css
│       ├── js/app.js
│       └── favicon.ico
├── requirements.txt
└── run.py
```

## 3. 실행 방법

### 3.1 Python 환경 준비

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3.2 환경 변수 파일 준비

현재 코드상 설정은 `config/settings.py`가 `config/.env`를 읽도록 되어 있습니다.

예시:

```env
APP_ENV=development
APP_HOST=0.0.0.0
APP_PORT=8000

OLLAMA_BASE_URL=http://localhost:11434
```

주의:

- 현재 저장소에는 `config/.env.example`이 보이지 않습니다. 문서에만 언급되던 상태였고, 실제로는 직접 `config/.env`를 만들어야 합니다.
- 현재 핵심 런타임 기준 필수 설정은 `APP_*`와 `OLLAMA_BASE_URL`입니다.
- `config/settings.py`에는 DB 관련 설정도 남아 있지만, 현재 앱의 핵심 기능과 헬스체크는 DB 연결을 요구하지 않습니다.

### 3.3 Ollama 준비

현재 모델 레지스트리는 모두 Ollama 기반입니다.

```bash
ollama pull glm-4.7-flash:Q4_K_M
ollama pull gemma3:27b
ollama pull qwen2.5-coder:32b
ollama serve
```

### 3.4 서버 실행

```bash
python run.py
```

또는

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

접속 경로:

- `/` 프런트엔드
- `/docs` Swagger UI
- `/api/health`
- `/api/models`
- `/api/convert`
- `/api/compare`

## 4. 설정과 런타임 동작

### 4.1 `config/settings.py`

이 파일이 프로젝트 전체 설정의 단일 진실 공급원입니다.

- 앱 포트/호스트
- Ollama 주소
- 레거시 DB 설정 항목

다른 모듈은 직접 환경변수를 읽지 않고 `settings` 객체를 참조합니다.

### 4.2 DB 관련 코드의 현재 위치

`backend/db/connection.py`가 DB 전환을 담당합니다.

- `DB_MODE=mssql`이면 `pyodbc.connect(...)`
- `DB_MODE=postgresql`이면 `psycopg2.connect(...)`

`db_context()`는 컨텍스트 종료 시 자동으로 commit/rollback/close를 수행합니다.  
`get_db_conn()`은 FastAPI `Depends(...)` 용 generator입니다.  
`ping()`은 `SELECT 1`을 호출해 DB 상태를 확인합니다.

중요한 점:

- 변환 기능 자체는 DB 연결 없이도 동작합니다.
- 현재 `/api/health`는 DB ping을 수행하지 않습니다.
- 생성되는 Python 예제 코드는 DB 연결 객체 `conn`을 인자로 받는 형태를 전제로 합니다.
- 즉, DB 관련 코드는 "생성 결과의 예시 문맥"과 "향후 확장 여지"에 가깝고, 현재 서버 핵심 런타임 의존성은 아닙니다.

## 5. 요청 흐름

### 5.1 앱 시작

`run.py` 실행
→ `backend.main:app` 로드
→ 로깅 초기화
→ CORS 등록
→ API 라우터 등록
→ `/static`, `/favicon.ico`, `/` 프런트엔드 라우트 등록

### 5.2 단일 변환 흐름

`POST /api/convert`
→ `ConvertRequest` 검증
→ `convert_single(...)`
→ 프로시저명 추출
→ few-shot system prompt 생성
→ user prompt 생성
→ 선택한 LLM 어댑터 호출
→ LLM 텍스트에서 코드 블록/섹션 파싱
→ `ConvertResponse` 반환

실제 핵심 함수는 `backend/services/converter/single.py`의 `convert_single()`입니다.

### 5.3 모델 비교 흐름

`POST /api/compare`
→ `CompareRequest` 검증
→ 각 모델별 `convert_single(...)` 병렬 실행
→ 각 결과에 대해 `score_code(...)` 수행
→ 최고 점수 모델 선정
→ GLM 모델로 종합 코멘트 생성
→ `CompareResponse` 반환

실제 핵심 함수는 `backend/services/converter/compare.py`의 `compare_models()`입니다.

## 6. 변환이 어떻게 만들어지는가

### 6.1 프롬프트 조립

`backend/fewshot/builder.py`가 system prompt를 조립합니다.

포함되는 정보:

- 타겟 DB 메타데이터
- 플레이스홀더 규칙
- import 예시
- 네이밍 규칙
- SQL → Python 변환 규칙
- 선택 옵션에 따른 추가 출력 섹션 지시
- `fewshot/examples.yaml`의 예시들

옵션별 영향:

- `include_tests=true`면 `[TEST CODE]` 섹션을 요구합니다.
- `include_fastapi_router=true`면 `[FASTAPI ROUTER]` 섹션을 요구합니다.
- 둘 중 하나라도 켜지면 `[SELF CHECK]` 섹션도 요구합니다.

### 6.2 모델 호출

`backend/llm/client.py`는 모델 ID를 어댑터 팩토리로 연결합니다.

현재 등록된 모델:

- `glm-4.7-flash-q4km`
- `gemma3-27`
- `qwen2.5coder-32b`

`backend/llm/adapters/ollama_adapter.py`는 Ollama `/api/chat`에 비스트리밍 요청을 보냅니다.

응답에서 사용하는 값:

- `message.content` → 최종 텍스트
- `eval_count + prompt_eval_count` → 총 토큰 수
- 호출 전후 시간차 → `elapsed_ms`

### 6.3 출력 파싱

`backend/services/converter/parser.py`가 다음 처리를 수행합니다.

- SQL에서 프로시저 이름 추출
- 마크다운 코드 펜스 제거
- `[MAIN CODE]`, `[TEST CODE]`, `[FASTAPI ROUTER]`, `[SELF CHECK]` 헤더 기반 섹션 분리

현재 응답 스키마에는 `SELF CHECK` 결과를 별도 필드로 담지 않습니다. 즉, 모델이 self check를 생성해도 API 응답에는 보존되지 않습니다.

## 7. API 스키마

### 7.1 `POST /api/convert`

요청:

```json
{
  "sql_code": "CREATE PROCEDURE ...",
  "target_db": "mssql",
  "model_id": "glm-4.7-flash-q4km",
  "include_tests": false,
  "include_fastapi_router": false
}
```

응답:

```json
{
  "success": true,
  "procedure_name": "GetEmployeeByDept",
  "target_db": "mssql",
  "model_id": "glm-4.7-flash-q4km",
  "python_code": "import pyodbc\n...",
  "test_code": null,
  "router_code": null,
  "line_count": 42,
  "tokens": 1304,
  "elapsed_ms": 8123,
  "error": null
}
```

특징:

- 변환 실패 시에도 서비스 레이어는 `success=false`인 응답 객체를 만들 수 있습니다.
- API 라우트는 `success=false`면 HTTP 500으로 변환합니다.

### 7.2 `POST /api/compare`

요청:

```json
{
  "sql_code": "CREATE PROCEDURE ...",
  "target_db": "postgresql",
  "model_ids": [
    "glm-4.7-flash-q4km",
    "gemma3-27",
    "qwen2.5coder-32b"
  ]
}
```

응답:

```json
{
  "success": true,
  "procedure_name": "CreateOrder",
  "results": [
    {
      "convert": {
        "success": true,
        "procedure_name": "CreateOrder",
        "target_db": "postgresql",
        "model_id": "glm-4.7-flash-q4km",
        "python_code": "...",
        "test_code": null,
        "router_code": null,
        "line_count": 55,
        "tokens": 1430,
        "elapsed_ms": 7610,
        "error": null
      },
      "score": {
        "correctness": 25,
        "type_hints": 20,
        "sql_safety": 20,
        "error_handling": 20,
        "readability": 11,
        "total": 96,
        "strengths": ["타입 힌트 완성"],
        "weaknesses": [],
        "verdict": "우수 (96/100) ..."
      }
    }
  ],
  "winner_model": "glm-4.7-flash-q4km",
  "winner_label": "GLM 4.7 Flash (Q4_K_M)",
  "ai_summary": "..."
}
```

## 8. 비교 점수는 어떻게 계산되는가

`backend/services/converter/scorer.py`는 휴리스틱 기반으로 100점 만점 점수를 계산합니다.

- 문법 정확성 25점
- 타입 힌트 20점
- SQL 안전성 20점
- 예외 처리 20점
- 가독성 15점

대표 규칙:

- 함수 정의, import, `cursor.execute`, `conn.commit/rollback` 존재 여부 확인
- 타입 힌트 문법 검색
- f-string SQL, `.format(...)` 사용 시 감점
- `try/except Exception`, `rollback()` 확인
- docstring, 주석, 평균 줄 길이 반영

이 점수는 빠르고 결정적이지만, 아래 한계가 있습니다.

- 실제 Python 문법 파싱이 아니라 정규식 기반입니다.
- SQL 의미 보존 여부는 검증하지 않습니다.
- 코드가 실행되는지 테스트하지 않습니다.
- 테스트 코드나 라우터 코드는 채점 대상이 아닙니다.

## 9. 프런트엔드 동작

프런트엔드는 `frontend/index.html` + `frontend/static/js/app.js` 조합으로 동작합니다.

### 9.1 단일 변환 화면

기능:

- 모델 카드 선택
- 타겟 DB 선택
- 테스트 코드 생성 여부 선택
- FastAPI 라우터 생성 여부 선택
- 예시 프로시저 삽입
- 최근 입력 SQL 5개 로컬 저장
- 결과 탭 전환
- 결과 복사

로컬 저장소:

- 키: `sql2python_recent_sql`
- 최근 SQL 최대 5개

### 9.2 비교 화면

기능:

- 모델 2개 이상 선택
- 타겟 DB 선택
- 예시 프로시저 삽입
- 병렬 비교 요청
- 점수 테이블 렌더링
- 항목별 미니 바차트 렌더링
- 모델별 생성 코드 카드 표시

주의:

- 프런트의 모델 목록은 백엔드 `/api/models`를 읽지 않고 JS 상수로 하드코딩되어 있습니다.
- 백엔드 레지스트리와 프런트 상수가 어긋나면 UI와 실제 지원 모델이 달라질 수 있습니다.

## 10. 파일별 책임 요약

### 백엔드

- `run.py`
  서버 실행 진입점

- `backend/main.py`
  FastAPI 앱 생성, CORS, 라우터, 정적 파일 서빙

- `backend/api/routes/health.py`
  헬스체크 및 모델 목록 응답

- `backend/api/routes/convert.py`
  단일 변환 엔드포인트

- `backend/api/routes/compare.py`
  다중 모델 비교 엔드포인트

- `backend/services/converter/single.py`
  프롬프트 생성, 모델 호출, 응답 파싱

- `backend/services/converter/compare.py`
  병렬 실행, 점수화, 승자 선정, AI 요약

- `backend/services/converter/parser.py`
  프로시저명 추출과 출력 섹션 파싱

- `backend/services/converter/scorer.py`
  규칙 기반 자동 채점

- `backend/fewshot/builder.py`
  few-shot prompt 조립

- `backend/llm/client.py`
  모델 메타데이터 레지스트리와 어댑터 선택

- `backend/llm/adapters/ollama_adapter.py`
  Ollama HTTP 호출

### 프런트엔드

- `frontend/index.html`
  단일 변환/비교 UI 마크업

- `frontend/static/js/app.js`
  상태 관리, fetch 호출, 렌더링

- `frontend/static/css/style.css`
  전체 스타일 정의

## 11. 새 모델 추가 방법

현재 구조에서는 다음 순서로 추가합니다.

1. `backend/llm/adapters/`에 어댑터 구현
2. `backend/llm/client.py`의 `MODEL_REGISTRY`에 등록
3. 프런트엔드 `frontend/static/js/app.js`의 `CONFIG.models`도 같이 갱신
4. 비교 화면 체크박스와 단일 변환 카드에 노출되는지 확인

중요:

- 현재 README 예전 버전처럼 "레지스트리만 바꾸면 끝"은 아닙니다.
- 프런트가 모델 목록을 별도로 하드코딩하고 있기 때문에 실제로는 백엔드와 프런트를 같이 수정해야 합니다.

## 12. 현재 구조의 장점

- 구조가 작고 단순해서 추적이 쉽습니다.
- 변환 로직과 비교 로직이 명확히 분리되어 있습니다.
- 모델 호출 추상화 계층이 얇아 새 어댑터 추가가 어렵지 않습니다.
- 프런트가 빌드 과정 없이 정적 파일이라 배포가 단순합니다.
- 비교 점수 계산이 빠르고 재현 가능합니다.

## 13. 현재 구조의 한계와 개선 포인트

### 13.1 문서/구성 불일치

- 문서에는 `config/.env.example`이 언급되지만 저장소에 보이지 않습니다.
- 개선:
  실제 예시 파일을 추가하고, 필수/선택 환경변수를 분리해 명시하는 것이 좋습니다.

### 13.2 프런트/백엔드 모델 정의 중복

- 모델 목록이 `backend/llm/client.py`와 `frontend/static/js/app.js` 양쪽에 하드코딩되어 있습니다.
- 개선:
  프런트는 `/api/models`를 호출해 동적으로 렌더링하도록 바꾸는 것이 맞습니다.

### 13.3 Self-check 결과 유실

- prompt는 `[SELF CHECK]`를 요구하지만 API 응답에는 담지 않습니다.
- 개선:
  `ConvertResponse`에 `self_check` 필드를 추가하거나, 섹션 파서를 확장해 그대로 보존해야 합니다.

### 13.4 비교 점수의 신뢰성 한계

- 현재 채점은 정규식 기반이라 실제 실행 가능성과 의미 보존을 보장하지 않습니다.
- 개선:
  `ast.parse()` 문법 검증, 샘플 입력 기반 스모크 테스트, SQL 의미 비교 규칙을 추가하는 것이 좋습니다.

### 13.5 예외 처리 정책이 일관되지 않음

- `/api/convert`는 `success=false`를 HTTP 500으로 바꾸고,
- `/api/compare`는 broad exception을 직접 문자열로 감싸 HTTP 500을 반환합니다.
- 개선:
  서비스 계층에서 도메인 예외를 일관되게 던지고, API 계층에서 공통 핸들러로 변환하는 구조가 더 안정적입니다.

### 13.6 전역 CORS 전체 허용

- 현재 `allow_origins=["*"]`입니다.
- 개선:
  운영 환경에서는 허용 origin을 환경변수로 제한해야 합니다.

### 13.7 테스트 부재

- 저장소에는 자동 테스트 코드가 없습니다.
- 개선:
  최소한 아래 테스트는 필요합니다.
  - parser 단위 테스트
  - scorer 단위 테스트
  - convert/compare API 테스트
  - Ollama 어댑터 mocking 테스트

### 13.8 비교 결과의 실패 모델 처리

- 비교 시 변환 실패 모델도 그대로 점수화되며, 전체 비교 응답은 성공으로 반환됩니다.
- 개선:
  부분 실패 여부를 별도 필드로 드러내고, AI 요약 prompt에도 실패 상태를 명시적으로 넣는 편이 낫습니다.

### 13.9 DB 모드와 생성 코드의 관계

- 앱의 `DB_MODE`는 현재 핵심 API 동작에는 직접 영향이 거의 없고,
- 변환 요청의 `target_db`는 생성 코드 스타일에 영향을 줍니다.
- 이 둘은 별개인데 사용자 입장에서는 혼동될 수 있습니다.
- 개선:
  문서와 UI에서 "서버 연결 DB"와 "생성 대상 DB 코드"를 분리해서 표현하는 것이 좋습니다.

## 14. 운영 시 체크리스트

- `config/.env`가 준비되었는지
- Ollama 서버가 살아 있는지
- 필요한 모델을 모두 pull 했는지
- `/api/health`가 통과하는지
- `/api/models`가 기대한 모델 목록을 반환하는지
- 긴 SQL 입력에서 Ollama 타임아웃이 없는지

## 15. 추천 다음 작업

현재 프로젝트를 안정화하려면 우선순위는 아래 순서가 적절합니다.

1. `config/.env.example` 추가
2. 프런트 모델 목록을 `/api/models` 기반 동적 렌더링으로 전환
3. parser/scorer/API 테스트 추가
4. `SELF CHECK` 응답 보존
5. 비교 점수 로직에 실제 문법 검사 추가

## 16. 요약

이 프로젝트는 "SQL 프로시저를 LLM으로 Python 코드로 변환하고, 여러 모델 출력을 빠르게 비교"하는 데 초점이 맞춰져 있습니다. 구조는 단순하고 확장 가능하지만, 현재 상태는 실험/내부 도구로는 충분해도 운영 품질로 가기 위해서는 문서 정합성, 테스트, 모델 정의 단일화, 응답 구조 보강이 필요합니다.
