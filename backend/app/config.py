from pathlib import Path

from pydantic_settings import BaseSettings

# 使用絕對路徑，確保無論從哪個目錄啟動都能找到 .env
_env_file = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/disaster_report"
    ANTHROPIC_API_KEY: str = ""
    # CLAUDE_MODEL: str = "claude-haiku-4-5-20251001"
    CLAUDE_MODEL: str = "gpt-5.4"
    # CLAUDE_MODEL: str = "claude-opus-4-6"
    GOOGLE_MAPS_API_KEY: str = ""
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 480
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:5174"

    model_config = {"env_file": str(_env_file)}


settings = Settings()
