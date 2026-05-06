from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings

# 使用絕對路徑，確保無論從哪個目錄啟動都能找到 .env
_env_file = Path(__file__).resolve().parents[1] / ".env"

# JWT_SECRET_KEY 最小長度（建議 32 字元 = 256 bits 隨機熵，等同 HMAC-SHA256 block size）
_JWT_MIN_LENGTH = 32

# 已知弱值黑名單：歷史硬編碼預設、常見 placeholder。validator 會拒絕這些值，
# 防止部署者沿用弱密鑰而導致 JWT 可被偽造。
_JWT_WEAK_KEYS = frozenset(
    {
        "",
        "change-me-in-production",
        "changeme",
        "secret",
        "ASDASAPWDJASDD46546D4ASD4A4D3D4",
    }
)


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/disaster_report"
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_BASE_URL: str = "https://api.banana2556.com"
    # CLAUDE_MODEL: str = "claude-haiku-4-5-20251001"
    CLAUDE_MODEL: str = "gpt-5.5"
    # CLAUDE_MODEL: str = "claude-opus-4-6"
    DEDUP_MODEL: str = "claude-sonnet-4-6"
    GOOGLE_MAPS_API_KEY: str = ""
    # 無預設值：必須透過環境變數提供強隨機密鑰；不合格值由 validator 擋下
    JWT_SECRET_KEY: str = "fGRmTRoRxEQHlbIKrJtauBjrk4ufBhlA"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 480
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:5174"

    # DB SSL：生產環境設 True 強制 sslmode=require，確保帳密加密傳輸。
    # 本機 docker-compose 通常無 SSL 憑證，預設 False。
    DB_REQUIRE_SSL: bool = False

    model_config = {"env_file": str(_env_file)}

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def _validate_jwt_secret(cls, v: str) -> str:
        if v in _JWT_WEAK_KEYS:
            raise ValueError(
                "JWT_SECRET_KEY 不可為空或已知弱值。請在 .env 設定強隨機字串，"
                "例如 `openssl rand -hex 32` 產生 64 字元 hex。"
            )
        if len(v) < _JWT_MIN_LENGTH:
            raise ValueError(
                f"JWT_SECRET_KEY 長度必須至少 {_JWT_MIN_LENGTH} 字元，"
                "建議使用 `openssl rand -hex 32` 產生。"
            )
        return v


settings = Settings()
