# SQL2Python 프로젝트 리뷰

작성일: 2026-04-09  
기준 코드 상태: 현재 워크트리 반영본

## 범위

- FastAPI 엔트리포인트, API 라우트, 변환/비교 서비스
- LLM 어댑터 및 모델 레지스트리
- 정적 프런트엔드 비교 UI
- 문법 수준 정적 검증

## 한줄 평가

현재 프로젝트는 "실패 상태를 성공처럼 보이게 만드는 문제"를 상당 부분 정리했고, 내부 데모/실험용으로는 구조가 안정됐습니다. 남은 핵심 과제는 모델 메타데이터 중복, 휴리스틱 점수 한계, 운영 설정 보수성입니다.

## 현재 강점

- 백엔드 책임 분리가 명확합니다. 라우트, 서비스, 스키마, 프롬프트 조립, LLM 어댑터가 분리돼 있어 추적이 쉽습니다.
- 비교 API가 이제 전체 실패, 부분 실패, 정상 완료를 구분해 응답합니다.
- 점수기가 최소한의 문법 검사를 포함해 "깨진 코드 고득점" 가능성을 줄였습니다.
- 비교 UI가 실패 모델을 눈에 띄게 표시하므로 결과 해석성이 좋아졌습니다.
- `/api/health`가 DB 의존성 없이 앱 상태와 모델 메타만 확인하므로 현재 프로젝트 성격에 더 맞습니다.

## 이번 점검에서 확인한 개선 완료 항목

### 1. 비교 실패 상태 표현 개선 완료

- 위치: [backend/services/converter/compare.py](/home/keti_spark1/yune/sql2python_v2/sql2python/backend/services/converter/compare.py)
- 이전에는 모든 모델이 실패해도 winner를 뽑을 수 있는 구조였는데, 지금은 성공 결과와 실패 결과를 분리합니다.
- 성공 모델이 하나도 없으면 `CompareResponse.success=False`로 종료합니다.
- 일부만 실패한 경우 `partial_failure`, `failed_models`를 응답에 담아 프런트가 상태를 설명할 수 있습니다.

### 2. 비교 라우트 예외 처리 단순화 완료

- 위치: [backend/api/routes/compare.py](/home/keti_spark1/yune/sql2python_v2/sql2python/backend/api/routes/compare.py)
- broad `except Exception`이 제거됐습니다.
- 라우트가 서비스 결과를 그대로 반환하므로 전역 예외 체계와 충돌이 줄었습니다.

### 3. 점수기 문법 검증 보강 완료

- 위치: [backend/services/converter/scorer.py](/home/keti_spark1/yune/sql2python_v2/sql2python/backend/services/converter/scorer.py)
- `ast.parse()` 기반 문법 검사 추가
- 문법 오류 시 correctness를 낮게 제한하고 total 상한도 제한
- weakness에 문법 오류를 직접 남겨 디버깅 가능성 개선

### 4. 비교 UI 실패 표시 보강 완료

- 위치: [frontend/index.html](/home/keti_spark1/yune/sql2python_v2/sql2python/frontend/index.html), [frontend/static/js/app.js](/home/keti_spark1/yune/sql2python_v2/sql2python/frontend/static/js/app.js), [frontend/static/css/style.css](/home/keti_spark1/yune/sql2python_v2/sql2python/frontend/static/css/style.css)
- 전체 실패와 부분 실패 시 상단 경고 박스 표시
- 실패 모델 행 강조
- 결과 카드에 `FAILED` 배지 표시

### 5. 헬스체크 단순화 완료

- 위치: [backend/api/routes/health.py](/home/keti_spark1/yune/sql2python_v2/sql2python/backend/api/routes/health.py)
- 현재 `/api/health`는 DB ping을 하지 않습니다.
- 앱 이름, 상태, 등록 모델 수만 반환하므로 현재 서비스 목적과 더 잘 맞습니다.

## 현재 남아 있는 주요 이슈

### 1. 프런트엔드와 백엔드가 모델 목록을 이중 관리함

- 위치: [frontend/static/js/app.js](/home/keti_spark1/yune/sql2python_v2/sql2python/frontend/static/js/app.js#L20), [backend/llm/client.py](/home/keti_spark1/yune/sql2python_v2/sql2python/backend/llm/client.py#L43)
- 프런트는 `CONFIG.models`를 하드코딩하고, 백엔드는 `MODEL_REGISTRY`를 따로 가집니다.
- 모델 추가, 이름 변경, 색상 수정 시 두 군데를 동시에 바꿔야 합니다.
- 현재 가장 명확한 구조적 부채입니다.

### 2. 점수기는 여전히 휴리스틱 중심이라 의미 보존까지는 검증하지 못함

- 위치: [backend/services/converter/scorer.py](/home/keti_spark1/yune/sql2python_v2/sql2python/backend/services/converter/scorer.py)
- 문법 검사는 추가됐지만, 여전히 점수의 대부분은 정규식과 휴리스틱입니다.
- SQL 의미 보존, 트랜잭션 의도, 반환 구조 일치 여부는 충분히 검증하지 못합니다.
- 따라서 scorer는 "품질 판정기"보다는 "깨진 결과 탈락 필터"에 가깝습니다.

### 3. CORS가 모든 환경에서 전체 허용임

- 위치: [backend/main.py](/home/keti_spark1/yune/sql2python_v2/sql2python/backend/main.py#L37)
- `allow_origins=["*"]`가 그대로입니다.
- 현재 내부 도구에는 큰 문제 아닐 수 있지만, `production` 설정이 존재하는 프로젝트 치고는 운영 보수성이 낮습니다.

### 4. 테스트 부재

- 저장소 기준 별도 자동 테스트 파일을 확인하지 못했습니다.
- 현재 구조에서 최소 필요 테스트는 아래 수준입니다.
- `parser.py` 단위 테스트
- `scorer.py` 단위 테스트
- `compare_models()`의 전체 실패/부분 실패/정상 완료 케이스
- Ollama 어댑터 mocking 기반 API 테스트

### 5. 비교 응답은 확장됐지만 프런트 렌더링은 아직 서버 응답에 강하게 결합돼 있음

- 위치: [frontend/static/js/app.js](/home/keti_spark1/yune/sql2python_v2/sql2python/frontend/static/js/app.js)
- 현재는 응답 구조에 맞춰 직접 DOM을 조립하는 방식이라, 응답 필드가 조금만 더 바뀌어도 프런트 수정 범위가 커집니다.
- 지금 단계에서는 허용 가능하지만, 비교 UI 요구사항이 더 늘어나면 렌더링 함수 분리가 필요합니다.

## 우선순위 제안

1. 프런트 모델 목록을 `/api/models` 기반으로 동적 렌더링 전환
2. `compare_models()`와 `scorer.py` 테스트 추가
3. CORS를 설정값으로 외부화
4. scorer 역할을 "문법/안전성 필터"로 명확히 문서화하거나, 의미 비교 로직을 별도 계층으로 분리
5. 비교 UI 렌더링 로직을 상태별 함수로 분리

## 검증 메모

- `python -m compileall backend config run.py` 실행 성공
- 프런트는 정적 JS/CSS 구조라 별도 빌드 단계 없음
- 실제 Ollama 호출은 런타임 의존성 때문에 이번 리뷰 범위에서 실행하지 않음

## 결론

이 프로젝트는 현재 기준으로 초기에 지적했던 가장 큰 문제들, 특히 비교 실패 상태 표현과 점수기의 최소 문법 검증 부분을 이미 개선했습니다. 지금 남은 과제는 "정확도 강화"보다 "유지보수성 정리"에 더 가깝습니다. 즉 다음 단계는 기능 추가보다 모델 메타데이터 단일화와 테스트 보강이 우선입니다.
