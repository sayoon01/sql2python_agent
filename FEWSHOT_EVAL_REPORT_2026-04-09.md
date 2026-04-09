# Few-shot 100개 반영 평가 리포트

작성일: 2026-04-09

## 목적

`backend/fewshot/examples.yaml` 를 기존 소수 few-shot 구조에서 100개 예시 구조로 교체한 뒤, 실제 변환 품질이 좋아졌는지 다방면으로 확인한다.

이번 평가는 다음을 본다.

- 변환 정확성
- 드라이버 종속성 감소 여부
- 예외 처리 보존 여부
- 동적 SQL 안전성
- 지연 시간 / 토큰 사용량
- 현재 scorer 기준 점수 변화

## 비교 대상

### 이전 프롬프트

- git commit: `7021035`
- old `examples.yaml`: 4개 예시
- MSSQL / `pyodbc.Connection` 중심 few-shot

### 현재 프롬프트

- current `examples.yaml`: 100개 예시
- MSSQL 전용
- `conn.cursor()` 중심
- 특정 드라이버 import 비강제

## 환경

- 프로젝트 경로: `/home/keti_spark1/yune/sql2python_v2/sql2python`
- 실행일: 2026-04-09
- 모델: `glm-4.7-flash-q4km`
- 어댑터: Ollama `/api/chat`
- 평가 방식:
  - 동일 모델 고정
  - old prompt / new prompt 각각 독립 호출
  - hold-out SQL에 대해 실변환 수행
  - 결과 코드를 `score_code()`로 후처리 채점

## 프롬프트 크기 비교

- old prompt 길이: `6,435` chars
- new prompt 길이: `171,894` chars

해석:

- 현재 100개 few-shot 프롬프트는 이전보다 매우 크다.
- 모델이 매 요청마다 읽어야 하는 문맥량이 크게 늘었다.
- 이 차이가 지연 시간 증가의 직접 원인으로 보인다.

## 테스트 케이스

### Case 1. Inventory Snapshot

대상 패턴:

- 일반 SELECT + JOIN
- 계산 컬럼
- 날짜 비교

결과:

| 항목 | old (4개) | new (100개) |
|---|---:|---:|
| elapsed_ms | 60,957 | 198,988 |
| tokens | 5,374 | 49,715 |
| score_total | 96 | 76 |
| `pyodbc` 포함 | 예 | 아니오 |
| `try/except` | 예 | 아니오 |
| `rollback()` | 예 | 아니오 |

관찰:

- new 결과는 드라이버 종속성은 줄었다.
- 그러나 예외 처리와 rollback 이 빠졌다.
- 일반 조회 함수인데 old 출력은 불필요하게 `try/except` 를 포함했고, scorer상 오히려 점수가 높게 나왔다.
- new 출력은 더 간결하지만 현재 scorer 기준에서는 감점되었다.

해석:

- 100개 few-shot은 `pyodbc.Connection` 강제를 줄이는 데는 성공했다.
- 하지만 현재 prompt/예시 조합은 단순 조회 함수에서도 예외 처리 보존을 일관되게 유도하지 못했다.
- 또한 토큰과 지연 시간이 크게 증가했다.

### Case 2. Versioned Update

대상 패턴:

- `ROWVERSION`
- `@@ROWCOUNT`
- OUTPUT BIT 반환

결과:

| 항목 | old (4개) | new (100개) |
|---|---:|---:|
| elapsed_ms | 40,775 | 213,091 |
| tokens | 4,309 | 49,840 |
| score_total | 96 | 68 |
| `pyodbc` 포함 | 예 | 아니오 |
| `bytes` 타입 보존 | 예 | 예 |
| `try/except` | 예 | 아니오 |
| `rollback()` | 예 | 아니오 |

관찰:

- new 결과도 `ROWVERSION -> bytes` 변환 자체는 유지했다.
- 그러나 예외 처리 구조가 사라졌다.
- scorer는 new 코드에 `T-SQL 구문 잔재` 약점을 부여했다.

해석:

- 100개 few-shot은 특정 SQL Server 개념을 아예 잃지는 않았다.
- 하지만 old prompt 대비 코드 안정성 패턴은 약해졌다.
- 특히 `UPDATE + commit + bool return` 수준으로 단순화되면서, 실패 경로 보존력이 낮아졌다.

### Case 3. Dynamic SQL Safety

대상 패턴:

- `sp_executesql`
- `QUOTENAME`
- 동적 테이블명
- ORDER BY 검증 필요

결과:

| 항목 | old (4개) | new (100개) |
|---|---:|---:|
| elapsed_ms | 58,614 | 430,880 |
| tokens | 4,847 | 52,326 |
| score_total | 39 | 61 |
| `pyodbc` 포함 | 예 | 아니오 |
| 화이트리스트 | 아니오 | 예 |
| ORDER BY 정규식 검증 | 아니오 | 예 |
| raw string concat | 예 | 아니오 |

관찰:

- old 결과는 사실상 unsafe dynamic SQL 이었다.
- old 코드는 `f"SELECT ... FROM {table_name}"`, `sql += f" ORDER BY {order_by}"` 형태로 생성되었다.
- new 결과는 `_ALLOWED_TABLES`, `_ORDER_RE` 를 만들고 검증 후 SQL 을 조립했다.
- 이 케이스에서는 new 결과가 명확히 더 낫다.

해석:

- 100개 few-shot의 가장 뚜렷한 개선점은 “희귀/복잡 패턴 커버리지”다.
- 특히 동적 SQL 보안 패턴은 old few-shot 보다 확실히 강화되었다.

## 종합 결과

### 좋아진 점

1. 드라이버 종속성 감소

- new 출력은 `pyodbc`, `pyodbc.Connection` 에 덜 묶였다.
- 현재 프로젝트 목표인 “MSSQL을 실행 가능한 Python 코드로 변환하는 agent” 방향에는 더 맞다.

2. 패턴 커버리지 확대

- 동적 SQL, 화이트리스트, ORDER BY 검증처럼 old 4예시가 약했던 영역은 개선되었다.
- 즉 100개 few-shot은 “모르는 패턴을 그럴듯하게 처리하는 능력”을 일부 높였다.

3. 특정 MSSQL 개념 유지

- `ROWVERSION -> bytes`
- SQL Server식 placeholder `?`
- OUTPUT 반환 구조
- JOIN / CTE / 윈도우 함수 유지

이런 축은 전반적으로 유지됐다.

### 나빠진 점

1. 지연 시간 급증

- new prompt는 모든 테스트에서 old 보다 훨씬 느렸다.
- 실제 측정:
  - 약 `3.3배`
  - 약 `5.2배`
  - 약 `7.3배`
  수준까지 증가

2. 토큰 사용량 급증

- old: 대략 `4k ~ 5k`
- new: 대략 `49k ~ 52k`

즉 실서비스 기준 비용/응답성 모두 불리하다.

3. 예외 처리 보존력 저하

- 두 hold-out 케이스에서 new 출력은 `try/except`, `rollback()` 이 사라졌다.
- old 출력은 오히려 이런 패턴을 더 자주 넣었다.
- 현재 scorer 기준으로도 new 쪽이 이 항목에서 일관되게 불리했다.

4. 타임아웃 리스크 증가

- 실제 테스트 중 기본 timeout 환경에서 new prompt 호출이 한 번 실패했다.
- 100개 few-shot 구조는 모델과 하드웨어 상태에 따라 timeout 리스크를 높인다.

## 결론

현재 100개 few-shot 반영은 “전면적인 품질 향상”이라고 보기는 어렵다.

더 정확히는:

- **좋아진 축**
  - 드라이버 중립성
  - 희귀 SQL 패턴 대응력
  - 동적 SQL 보안 인식

- **나빠진 축**
  - 응답 속도
  - 토큰 효율
  - 예외 처리 일관성
  - timeout 안정성

즉 이번 변경은 품질이 단순 상승한 것이 아니라, **성격이 바뀐 것**에 가깝다.

### 현재 판단

- “특정 드라이버 종속성을 줄이고 다양한 MSSQL 패턴을 많이 보여주고 싶다”는 목적에는 일부 성공
- “빠르고 안정적으로 실행 가능한 코드를 꾸준히 뽑고 싶다”는 목적에는 아직 미흡

## 권장 후속 조치

1. 100개 전부를 매번 넣지 말 것

- 현재 가장 큰 병목은 prompt 크기다.
- 예시 전체를 항상 넣는 대신, 주제별 예시를 선택 주입하는 구조가 필요하다.

추천 방향:

- `SELECT/JOIN`
- `OUTPUT/RETURN`
- `TRANSACTION/TRY-CATCH`
- `DYNAMIC SQL`
- `WINDOW/CTE`
- `BULK/BATCH`

같은 카테고리로 나누고, 입력 SQL 특징에 따라 6~12개 정도만 골라 넣는 방식이 적절하다.

2. 예외 처리 few-shot을 더 강하게 보강할 것

- 현재 100개 examples 는 패턴 다양성은 크지만, 모델이 예외 처리보다 “간결한 쿼리 래핑” 쪽으로 수렴하는 경향이 있다.
- `try/except + rollback + 명시적 실패 반환` 예시를 고품질로 따로 강화할 필요가 있다.

3. scorer 기준과 실제 목표를 더 맞출 것

- 현재 scorer는 예외 처리 존재를 강하게 점수화한다.
- 반면 new prompt는 일부 케이스에서 더 단순한 코드를 출력한다.
- “단순 SELECT에 try/except 가 꼭 필요한가?” 같은 정책을 먼저 정해야 한다.

4. 실제 운영 기준의 성능 가드레일이 필요

- prompt 길이 upper bound
- 모델별 timeout 기준
- 비교 모드와 단일 변환 모드의 separate prompt size limit

이런 제한이 필요하다.

## 최종 판정

현재 100개 few-shot 반영은:

- **보안/패턴 다양성 측면에서는 부분 개선**
- **성능/안정성 측면에서는 뚜렷한 회귀**

따라서 현 상태를 최종형으로 보기보다는, **100개 예시를 데이터 풀로 유지하고 실제 prompt에는 선택적으로 일부만 주입하는 구조로 개편하는 것이 가장 합리적**이다.

