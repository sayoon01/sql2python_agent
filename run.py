"""
run.py
=======
서버 실행 진입점.

사용법:
  python run.py
  uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
"""
import uvicorn
from config.settings import settings

if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=(settings.APP_ENV == "development"),
        log_level="info",
    )
