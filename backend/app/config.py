from pathlib import Path

from pydantic_settings import BaseSettings

# 使用絕對路徑，確保無論從哪個目錄啟動都能找到 .env
_env_file = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/disaster_report"
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_BASE_URL: str = "https://api.banana2556.com"
    # CLAUDE_MODEL: str = "claude-haiku-4-5-20251001"
    CLAUDE_MODEL: str = "gpt-5.4"
    # CLAUDE_MODEL: str = "claude-opus-4-6"
    DEDUP_MODEL: str = "claude-sonnet-4-6"
    GOOGLE_MAPS_API_KEY: str = ""
    JWT_SECRET_KEY: str = "ASDASAPWDJASDD46546D4ASD4A4D3D4"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 480
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:5174"

    # Twilio SMS
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_FROM_NUMBER: str = ""

    # LINE Messaging API
    LINE_CHANNEL_ACCESS_TOKEN: str = ""
    LINE_CHANNEL_SECRET: str = ""

    # SMTP Email
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_ADDRESS: str = ""

    # Clarification 安全門檻
    CLARIFICATION_DAILY_LIMIT: int = 500
    PUBLIC_BASE_URL: str = "http://localhost:5173"

    model_config = {"env_file": str(_env_file)}


settings = Settings()
