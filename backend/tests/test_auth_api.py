"""
認證 API 端點測試：POST /api/auth/login, GET /api/auth/me
"""
from datetime import datetime, timezone
from uuid import uuid4

from app.models.user import User
from app.services.auth_service import hash_password


# ---------------------------------------------------------------------------
# POST /api/auth/login
# ---------------------------------------------------------------------------
def test_login_success(client, mock_db):
    user = User(
        id=uuid4(),
        username="admin",
        hashed_password=hash_password("pass123"),
        display_name="管理員",
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    mock_db.query.return_value.filter.return_value.first.return_value = user

    response = client.post(
        "/api/auth/login",
        data={"username": "admin", "password": "pass123"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client, mock_db):
    user = User(
        id=uuid4(),
        username="admin",
        hashed_password=hash_password("pass123"),
        display_name="管理員",
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    mock_db.query.return_value.filter.return_value.first.return_value = user

    response = client.post(
        "/api/auth/login",
        data={"username": "admin", "password": "wrongpass"},
    )

    assert response.status_code == 401
    assert "帳號或密碼錯誤" in response.json()["detail"]


def test_login_nonexistent_user(client, mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = None

    response = client.post(
        "/api/auth/login",
        data={"username": "nobody", "password": "pass123"},
    )

    assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/auth/me
# ---------------------------------------------------------------------------
def test_get_me_authenticated(auth_client, test_user):
    response = auth_client.get("/api/auth/me")

    assert response.status_code == 200
    data = response.json()
    assert data["username"] == test_user.username
    assert data["display_name"] == test_user.display_name
    assert data["is_active"] is True


def test_get_me_no_token(client):
    response = client.get("/api/auth/me")

    assert response.status_code == 401


def test_get_me_invalid_token(client):
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer invalid-token-here"},
    )

    assert response.status_code == 401
