"""
認證服務單元測試：hash_password, verify_password, create_access_token, authenticate_user
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4

from jose import jwt

from app.config import settings
from app.models.user import User
from app.services.auth_service import (
    authenticate_user,
    create_access_token,
    hash_password,
    verify_password,
)


# ---------------------------------------------------------------------------
# hash_password / verify_password
# ---------------------------------------------------------------------------
def test_hash_password_returns_bcrypt_hash():
    hashed = hash_password("mypassword")
    assert hashed.startswith("$2b$") or hashed.startswith("$2a$")
    assert len(hashed) == 60


def test_verify_password_correct():
    hashed = hash_password("secret123")
    assert verify_password("secret123", hashed) is True


def test_verify_password_wrong():
    hashed = hash_password("secret123")
    assert verify_password("wrong", hashed) is False


# ---------------------------------------------------------------------------
# create_access_token
# ---------------------------------------------------------------------------
def test_create_access_token_contains_sub():
    token = create_access_token({"sub": "admin"})
    payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    assert payload["sub"] == "admin"


def test_create_access_token_contains_exp():
    token = create_access_token({"sub": "admin"})
    payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    assert "exp" in payload


# ---------------------------------------------------------------------------
# authenticate_user
# ---------------------------------------------------------------------------
def _make_user(username: str, password: str) -> User:
    return User(
        id=uuid4(),
        username=username,
        hashed_password=hash_password(password),
        display_name="Test",
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )


def test_authenticate_user_success():
    user = _make_user("admin", "pass123")
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = user

    result = authenticate_user(db, "admin", "pass123")
    assert result is user


def test_authenticate_user_wrong_password():
    user = _make_user("admin", "pass123")
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = user

    result = authenticate_user(db, "admin", "wrongpass")
    assert result is None


def test_authenticate_user_nonexistent():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None

    result = authenticate_user(db, "nobody", "pass123")
    assert result is None
