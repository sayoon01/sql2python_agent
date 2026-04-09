# SQL2Python Agent v2

MS SQL Server 저장 프로시저를 Python 함수 코드로 변환하고, 여러 LLM 결과를 비교 평가하는 FastAPI 기반 프로젝트입니다.

현재 구조는 다음 원칙으로 정리되어 있습니다.

- 실제 DB 연결 기능은 제거됨
- 생성 스타일은 MSSQL 실행 코드 기준으로 고정됨
- 백엔드 API와 정적 프런트엔드를 하나의 앱에서 함께 서빙함

## 실행 방법

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

또는

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

## 환경 변수

`config/settings.py`가 `config/.env`를 읽습니다.

예시:

```env
APP_ENV=development
APP_HOST=0.0.0.0
APP_PORT=8000

OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_TIMEOUT_SECONDS=180
OLLAMA_KEEP_ALIVE=10m
```

## 주요 경로

- `/` 프런트엔드
- `/docs` Swagger UI
- `/api/health`
- `/api/models`
- `/api/convert`
- `/api/compare`

## 현재 기능

### 1. 단일 변환

`POST /api/convert`

- 입력: MS SQL 저장 프로시저 문자열
- 출력: MSSQL 실행용 Python 함수 코드
- 옵션: 테스트 코드 포함, FastAPI 라우터 코드 포함

### 2. 모델 비교

`POST /api/compare`

- 같은 SQL 프로시저를 여러 모델에 동시에 전달
- 규칙 기반 scorer로 결과 점수화
- winner, 부분 실패 여부, 실패 모델 목록, AI 요약 반환

## 현재 구조

```text
sql2python/
├── backend/
│   ├── api/routes/
│   ├── core/
│   ├── fewshot/
│   ├── llm/
│   ├── schemas/
│   ├── services/converter/
│   └── main.py
├── config/settings.py
├── frontend/
├── requirements.txt
└── run.py
```

## 참고

- 이 프로젝트는 서버가 실제 SQL Server/PostgreSQL에 연결하지 않습니다.
- DB 연결 설정과 PostgreSQL 전환 기능은 제거되었습니다.
- 생성 코드는 MSSQL 규칙에 맞춘 일반 `conn.cursor()` 기반 실행 코드로 유도됩니다.
