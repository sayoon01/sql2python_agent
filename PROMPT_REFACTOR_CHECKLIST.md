# Prompt 리팩터링 체크리스트 메모

`backend/fewshot/builder.py` 관련.
현재는 **코드 변경 없이 유지**하고, 추후 필요 시 아래 항목 기준으로 정리한다.

## 현재 결정

- [x] 지금은 구조 변경하지 않고 유지
- [x] 중복 지시(규칙 + SELF CHECK)는 안정성 우선으로 허용

## 추후 리팩터링(선택)

### 1) 공통 규칙 블록 정리 (`## 변환 규칙`)
- [ ] 공통 원칙만 남기기
  - [ ] 즉시 실행 가능
  - [ ] import 누락 금지
  - [ ] 프로젝트 기준 모듈 경로 사용
- [ ] 테스트/라우터 세부 규칙은 공통 규칙에서 제거

### 2) 테스트 옵션 지시 집중 (`if include_tests`)
- [ ] 정상/실패/예외 케이스 분리 지시 유지
- [ ] `cursor.rowcount` 단계별 재현 지시
- [ ] `execute.side_effect` 예외 재현 지시
- [ ] `commit/rollback/execute` 호출 횟수/순서/인자 assert 지시

### 3) 라우터 옵션 지시 집중 (`if include_router`)
- [ ] `Depends(get_db_conn)` 패턴 유지
- [ ] 요청/응답 스키마와 메인 반환 구조 일치 지시
- [ ] 예외 발생 시 `HTTPException` 변환 지시

### 4) SELF CHECK 압축
- [ ] 상세 설명 대신 짧은 체크 키워드로 정리
  - [ ] import
  - [ ] module path
  - [ ] test branch coverage
  - [ ] transaction asserts
  - [ ] router schema
  - [ ] http exception

## 완료 기준(DoD)

- [ ] 프롬프트 길이는 줄었지만(중복 체감 완화), 강제력은 유지
- [ ] 공통/테스트/라우터/점검의 역할 분리가 명확
- [ ] 생성 품질 저하 없이 실행 가능성(누락 import/경로 오류) 유지

