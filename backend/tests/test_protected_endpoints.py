"""
受保護端點驗證：確認需要認證的端點在無 token 時回傳 401，有 token 時正常運作。
同時驗證公開端點不需要 token。
"""
from uuid import uuid4


# ---------------------------------------------------------------------------
# PUT /api/events/{id} — 需要認證
# ---------------------------------------------------------------------------
def test_update_event_requires_auth(client):
    response = client.put(f"/api/events/{uuid4()}", json={"severity": 3})
    assert response.status_code == 401


def test_update_event_with_auth(auth_client, fake_event, event_id, mocker):
    mocker.patch(
        "app.api.events.event_service.update_event",
        return_value=fake_event,
    )
    response = auth_client.put(f"/api/events/{event_id}", json={"severity": 3})
    assert response.status_code == 200
    assert response.json()["severity"] == 3


# ---------------------------------------------------------------------------
# DELETE /api/events/{id} — 需要認證
# ---------------------------------------------------------------------------
def test_delete_event_requires_auth(client):
    response = client.delete(f"/api/events/{uuid4()}")
    assert response.status_code == 401


def test_delete_event_with_auth(auth_client, mocker):
    mocker.patch(
        "app.api.events.event_service.delete_event",
        return_value=True,
    )
    response = auth_client.delete(f"/api/events/{uuid4()}")
    assert response.status_code == 204


# ---------------------------------------------------------------------------
# PATCH /api/events/{id}/location — 需要認證
# ---------------------------------------------------------------------------
def test_patch_location_requires_auth(client):
    response = client.patch(
        f"/api/events/{uuid4()}/location",
        json={"location_text": "台北市"},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/llm-logs — 需要認證
# ---------------------------------------------------------------------------
def test_llm_logs_requires_auth(client):
    response = client.get("/api/llm-logs")
    assert response.status_code == 401


def test_llm_logs_with_auth(auth_client, mock_db):
    mock_db.query.return_value.order_by.return_value.limit.return_value.all.return_value = []
    response = auth_client.get("/api/llm-logs")
    assert response.status_code == 200
    assert response.json() == []


# ---------------------------------------------------------------------------
# 公開端點 — 不需要認證
# ---------------------------------------------------------------------------
def test_list_events_no_auth(client, mocker):
    mocker.patch(
        "app.api.events.event_service.get_events",
        return_value={
            "items": [],
            "total": 0,
            "page": 1,
            "page_size": 20,
            "total_pages": 0,
        },
    )
    response = client.get("/api/events")
    assert response.status_code == 200


def test_map_events_no_auth(client, mocker):
    mocker.patch(
        "app.api.events.event_service.get_map_events",
        return_value=[],
    )
    response = client.get("/api/events/map")
    assert response.status_code == 200


def test_get_event_no_auth(client, fake_event, event_id, mocker):
    mocker.patch(
        "app.api.events.event_service.get_event_by_id",
        return_value=fake_event,
    )
    response = client.get(f"/api/events/{event_id}")
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# GET /api/events/{id}/reports — 需要認證（含 PII）
# ---------------------------------------------------------------------------
def test_get_event_reports_requires_auth(client):
    response = client.get(f"/api/events/{uuid4()}/reports")
    assert response.status_code == 401


def test_get_event_reports_with_auth(auth_client, mock_db):
    mock_db.query.return_value.filter.return_value.all.return_value = []
    response = auth_client.get(f"/api/events/{uuid4()}/reports")
    assert response.status_code == 200
    assert response.json()["items"] == []


# ---------------------------------------------------------------------------
# GET /api/events/statistics、GET /api/events/export.csv — 需要認證
#
# 注意：撰寫本測試時 app/api/events.py 尚未定義這兩支路由（見
# tests/test_statistics.py 檔頭說明），故目前拿到的會是 404 而非 401，
# 這兩條測試現在會失敗；等路由補上後才會驗證到真正的認證行為。
# ---------------------------------------------------------------------------
def test_statistics_requires_auth(client):
    response = client.get("/api/events/statistics")
    assert response.status_code == 401


def test_export_csv_requires_auth(client):
    response = client.get("/api/events/export.csv")
    assert response.status_code == 401
