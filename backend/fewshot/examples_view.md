## `examples.yaml` 보기용 문서

`backend/fewshot/examples.yaml`을 읽기 쉽게 펼쳐 놓은 참고 문서입니다.  
실제 기준 파일은 YAML이며, 이 문서는 가독성용입니다.

현재 예시는 다음 원칙으로 구성됩니다.

- MS SQL 저장 프로시저 입력
- MSSQL 실행용 Python 코드 출력
- 특정 드라이버 타입 힌트 없이 `conn.cursor()` 기반 코드 예시

### SELECT 단건 조회

```sql
CREATE PROCEDURE GetUserByID
    @UserID   INT,
    @IsActive BIT = 1
AS
BEGIN
    SET NOCOUNT ON;
    SELECT UserID, Name, Email, CreatedAt
    FROM   Users
    WHERE  UserID   = @UserID
      AND  IsActive = @IsActive;
END
```

```python
from typing import Optional, Dict, Any


def get_user_by_id(
    conn,
    user_id: int,
    is_active: bool = True,
) -> Optional[Dict[str, Any]]:
    sql = """
        SELECT UserID, Name, Email, CreatedAt
        FROM   Users
        WHERE  UserID   = ?
          AND  IsActive = ?
    """
    cursor = conn.cursor()
    cursor.execute(sql, (user_id, int(is_active)))
    row = cursor.fetchone()
    if row is None:
        return None
    cols = [col[0] for col in cursor.description]
    return dict(zip(cols, row))
```

### INSERT + OUTPUT 파라미터

```sql
CREATE PROCEDURE CreateOrder
    @CustomerID  INT,
    @TotalAmount DECIMAL(18,2),
    @OrderID     INT OUTPUT
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        INSERT INTO Orders (CustomerID, TotalAmount, OrderDate)
        VALUES (@CustomerID, @TotalAmount, GETDATE());
        SET @OrderID = SCOPE_IDENTITY();
    END TRY
    BEGIN CATCH
        RAISERROR('주문 생성 실패', 16, 1);
    END CATCH
END
```

```python
from datetime import datetime


def create_order(
    conn,
    customer_id: int,
    total_amount: float,
) -> int:
    sql = """
        INSERT INTO Orders (CustomerID, TotalAmount, OrderDate)
        VALUES (?, ?, ?);
        SELECT CAST(SCOPE_IDENTITY() AS INT) AS NewID;
    """
    cursor = conn.cursor()
    try:
        cursor.execute(sql, (customer_id, total_amount, datetime.now()))
        row = cursor.fetchone()
        conn.commit()
        return int(row[0]) if row else -1
    except Exception as exc:
        conn.rollback()
        raise RuntimeError(f"주문 생성 실패: {exc}") from exc
```
