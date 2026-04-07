"""
backend/core/exceptions.py
===========================
앱 전용 예외 계층.
API 레이어에서 이 예외들을 잡아 HTTP 응답으로 변환합니다.
"""


class AppError(Exception):
    """모든 앱 예외의 기반 클래스"""
    def __init__(self, message: str, code: str = "APP_ERROR"):
        self.message = message
        self.code    = code
        super().__init__(message)


class LLMError(AppError):
    """LLM API 호출 실패"""
    def __init__(self, model_id: str, detail: str):
        super().__init__(
            message=f"[{model_id}] LLM 호출 실패: {detail}",
            code="LLM_ERROR",
        )
        self.model_id = model_id


class DBError(AppError):
    """DB 연결 또는 쿼리 실패"""
    def __init__(self, detail: str):
        super().__init__(message=f"DB 오류: {detail}", code="DB_ERROR")


class ConvertError(AppError):
    """코드 변환 로직 실패"""
    def __init__(self, detail: str):
        super().__init__(message=f"변환 실패: {detail}", code="CONVERT_ERROR")
