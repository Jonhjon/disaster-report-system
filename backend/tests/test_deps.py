"""
get_current_user 依賴測試：token 驗證邏輯
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from jose import jwt

from app.api.deps import get_current_user
from app.config import settings
from app.models.user import User


def _make_token(payload: dict, secret: str = settings.JWT_SECRET_KEY) -> str:
    return jwt.encode(payload, secret, algorithm=settings.JWT_ALGORITHM)


def _make_active_user() -> User:
    return User(
        id=uuid4(),
        username="admin",
        hashed_password="fakehash",
        display_name="管理員",
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )


def test_valid_token_returns_user():
    user = _make_active_user()
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = user

    exp = datetime.now(timezone.utc) + timedelta(hours=1)
    token = _make_token({"sub": "admin", "exp": exp})

    result = get_current_user(token=token, db=db)
    assert result is user


def test_expired_token_raises_401():
    db = MagicMock()
    exp = datetime.now(timezone.utc) - timedelta(hours=1)
    token = _make_token({"sub": "admin", "exp": exp})

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(token=token, db=db)
    assert exc_info.value.status_code == 401


def test_invalid_token_raises_401():
    db = MagicMock()

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(token="not-a-valid-jwt", db=db)
    assert exc_info.value.status_code == 401


def test_token_missing_sub_raises_401():
    db = MagicMock()
    exp = datetime.now(timezone.utc) + timedelta(hours=1)
    token = _make_token({"exp": exp})  # 沒有 sub

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(token=token, db=db)
    assert exc_info.value.status_code == 401


def test_inactive_user_raises_401():
    user = _make_active_user()
    user.is_active = False
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = user

    exp = datetime.now(timezone.utc) + timedelta(hours=1)
    token = _make_token({"sub": "admin", "exp": exp})

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(token=token, db=db)
    assert exc_info.value.status_code == 401


def test_user_not_found_raises_401():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None

    exp = datetime.now(timezone.utc) + timedelta(hours=1)
    token = _make_token({"sub": "ghost", "exp": exp})

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(token=token, db=db)
    assert exc_info.value.status_code == 401


def test_wrong_secret_raises_401():
    db = MagicMock()
    exp = datetime.now(timezone.utc) + timedelta(hours=1)
    token = _make_token({"sub": "admin", "exp": exp}, secret="wrong-secret-key")

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(token=token, db=db)
    assert exc_info.value.status_code == 401
