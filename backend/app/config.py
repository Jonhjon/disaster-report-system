from pathlib import Path

from pydantic_settings import BaseSettings

# 使用絕對路徑，確保無論從哪個目錄啟動都能找到 .env
_env_file = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/disaster_report"
    ANTHROPIC_API_KEY: str = ""
    CLAUDE_MODEL: str = "claude-haiku-4-5-20251001"
    GOOGLE_MAPS_API_KEY: str = ""

    model_config = {"env_file": str(_env_file)}


settings = Settings()
