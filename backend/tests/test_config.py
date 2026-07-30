"""
設定驗證測試：JWT 預設值與 CORS 分割
"""
from app.config import settings


def test_jwt_defaults():
    assert settings.JWT_ALGORITHM == "HS256"
    assert settings.JWT_EXPIRE_MINUTES == 480
    assert len(settings.JWT_SECRET_KEY) > 0


def test_cors_origins_split():
    origins = settings.CORS_ORIGINS.split(",")
    assert len(origins) >= 1
    for origin in origins:
        assert origin.startswith("http")
