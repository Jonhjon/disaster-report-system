"""
方向四：API 端點整合測試（8 案例）
策略：FastAPI TestClient + Mock get_db 依賴注入 + Mock service 函數
"""
from uuid import uuid4


# ---------------------------------------------------------------------------
# Case 15: GET /api/events 正常請求 → 200 + EventListResponse
# ---------------------------------------------------------------------------
def test_list_events_success(client, mocker):
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
    data = response.json()
    assert "items" in data
    assert data["total"] == 0
    assert data["page"] == 1


# ---------------------------------------------------------------------------
# Case 16: GET /api/events?page_size=0 → 422 Unprocessable
# ---------------------------------------------------------------------------
def test_list_events_invalid_page_size(client):
    response = client.get("/api/events?page_size=0")

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Case 17: GET /api/events/map?bounds=... → 200 + EventMapResponse
# ---------------------------------------------------------------------------
def test_map_events_with_bounds(client, mocker):
    mocker.patch(
        "app.api.events.event_service.get_map_events",
        return_value=[],
    )

    response = client.get("/api/events/map?bounds=24.9,121.4,25.1,121.6")

    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert isinstance(data["items"], list)


# ---------------------------------------------------------------------------
# Case 18: GET /api/events/{id} 存在的 ID → 200 + 正確欄位
# ---------------------------------------------------------------------------
def test_get_event_success(client, fake_event, event_id, mocker):
    mocker.patch(
        "app.api.events.event_service.get_event_by_id",
        return_value=fake_event,
    )

    response = client.get(f"/api/events/{event_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(event_id)
    assert data["disaster_type"] == "earthquake"
    assert data["severity"] == 3


# ---------------------------------------------------------------------------
# Case 19: GET /api/events/{id} 不存在的 UUID → 404
# ---------------------------------------------------------------------------
def test_get_event_not_found(client, mocker):
    mocker.patch(
        "app.api.events.event_service.get_event_by_id",
        return_value=None,
    )

    response = client.get(f"/api/events/{uuid4()}")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Case 20: PUT /api/events/{id} 更新 severity=3 → 200 + severity=3
# ---------------------------------------------------------------------------
def test_update_event_severity(auth_client, fake_event, event_id, mocker):
    mocker.patch(
        "app.api.events.event_service.update_event",
        return_value=fake_event,  # fake_event already has severity=3
    )

    response = auth_client.put(f"/api/events/{event_id}", json={"severity": 3})

    assert response.status_code == 200
    assert response.json()["severity"] == 3


# ---------------------------------------------------------------------------
# Case 21: PUT /api/events/{id} severity=99（非法）→ 422
# ---------------------------------------------------------------------------
def test_update_event_invalid_severity(auth_client, event_id):
    response = auth_client.put(f"/api/events/{event_id}", json={"severity": 99})

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Case 22: GET /api/reports 正常請求 → 200 + ReportListResponse
# ---------------------------------------------------------------------------
def test_list_reports_success(client, mock_db):
    mock_db.query.return_value.count.return_value = 0
    (
        mock_db.query.return_value
        .order_by.return_value
        .offset.return_value
        .limit.return_value
        .all.return_value
    ) = []

    response = client.get("/api/reports")

    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert data["total"] == 0
    assert isinstance(data["items"], list)
