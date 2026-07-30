"""Chat 流程帶照片附件的整合測試。

驗證綁定 helper 與 _create_new_event / _merge_into_event 內的整合：
- 帶 attachment_ids 時，未綁定的 attachment 應被綁定到新 Report
- 已綁定（report_id IS NOT NULL）的不應被重綁，避免跨報告盜用
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.report_attachment import ReportAttachment
from app.schemas.llm_tools import SubmitDisasterReportPayload


def _coords():
    return {
        "latitude": 25.033,
        "longitude": 121.565,
        "display_name": "台北市信義區市府路45號",
        "source": "google_places",
    }


def _tool_data(**overrides):
    data = {
        "disaster_type": "fire",
        "description": "建物起火",
        "location_text": "台北市信義區市府路45號",
        "severity": 3,
        "casualties": 0,
        "injured": 0,
        "trapped": 0,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "reporter_name": "測試者",
        "reporter_phone": "0900000000",
    }
    data.update(overrides)
    return SubmitDisasterReportPayload.model_validate(data)


def _attachment(id_=None, report_id=None) -> ReportAttachment:
    a = ReportAttachment(
        filename=f"{uuid.uuid4().hex}.jpg",
        original_filename="photo.jpg",
        content_type="image/jpeg",
        size_bytes=1024,
    )
    a.id = id_ or uuid.uuid4()
    a.report_id = report_id
    return a


def _mock_db_with_attachments(attachments_to_return):
    """Mock 出 db，db.query(ReportAttachment).filter(...).all() 會回 attachments_to_return。

    其他 query（dedup 等）一律回空。
    """
    mock_db = MagicMock()
    mock_db.get.return_value = None

    # 用 side_effect 區分 query target
    def _query_side_effect(model):
        q = MagicMock()
        if model is ReportAttachment:
            q.filter.return_value.all.return_value = attachments_to_return
        else:
            q.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
            q.filter.return_value.all.return_value = []
            q.order_by.return_value.limit.return_value.all.return_value = []
        return q

    mock_db.query.side_effect = _query_side_effect
    return mock_db


# ---------------------------------------------------------------------------
# Helper unit tests
# ---------------------------------------------------------------------------


def test_bind_attachments_binds_unassigned_only():
    """已綁定的 attachment 不會被重新綁定（DB 層 filter report_id IS NULL）。"""
    from app.api.chat import _bind_attachments_to_report

    other_report_id = uuid.uuid4()
    unbound = _attachment(report_id=None)
    bound = _attachment(report_id=other_report_id)

    # mock_db.filter 模擬 SQL filter 已過濾掉已綁定的，所以只回 unbound
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.all.return_value = [unbound]

    new_report_id = uuid.uuid4()
    count = _bind_attachments_to_report(
        mock_db, [str(unbound.id), str(bound.id)], new_report_id
    )

    assert count == 1
    assert unbound.report_id == new_report_id
    # bound 沒被傳入 helper 處理，report_id 保持原樣
    assert bound.report_id == other_report_id


def test_bind_attachments_empty_list_noop():
    """attachment_ids 為空時不查 DB、不寫入。"""
    from app.api.chat import _bind_attachments_to_report

    mock_db = MagicMock()
    count = _bind_attachments_to_report(mock_db, [], uuid.uuid4())

    assert count == 0
    mock_db.query.assert_not_called()


# ---------------------------------------------------------------------------
# Integration with _create_new_event
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_new_event_binds_attachments():
    """新建事件時，attachment_ids 中未綁定的應被綁到新建的 Report。"""
    from app.api.chat import _process_tool_use

    unbound = _attachment(report_id=None)
    mock_db = _mock_db_with_attachments([unbound])

    captured_reports = []

    def _add(obj):
        from app.models.disaster_report import DisasterReport

        if isinstance(obj, DisasterReport):
            obj.id = uuid.uuid4()
            captured_reports.append(obj)
        else:
            obj.id = uuid.uuid4()

    mock_db.add.side_effect = _add

    with (
        patch("app.api.chat.get_broker") as mock_broker,
        patch(
            "app.api.chat.find_and_score_candidates",
            new_callable=AsyncMock,
            return_value=[],
        ),
    ):
        mock_broker.return_value.publish = AsyncMock()
        result = await _process_tool_use(
            _tool_data(),
            "原始訊息",
            mock_db,
            _coords(),
            attachment_ids=[str(unbound.id)],
        )

    assert result["status"] == "created"
    assert len(captured_reports) == 1
    assert unbound.report_id == captured_reports[0].id


@pytest.mark.asyncio
async def test_create_new_event_no_attachments_works():
    """不帶 attachment_ids 也應正常建立事件。"""
    from app.api.chat import _process_tool_use

    mock_db = _mock_db_with_attachments([])

    def _add(obj):
        obj.id = uuid.uuid4()

    mock_db.add.side_effect = _add

    with (
        patch("app.api.chat.get_broker") as mock_broker,
        patch(
            "app.api.chat.find_and_score_candidates",
            new_callable=AsyncMock,
            return_value=[],
        ),
    ):
        mock_broker.return_value.publish = AsyncMock()
        result = await _process_tool_use(
            _tool_data(),
            "原始訊息",
            mock_db,
            _coords(),
        )

    assert result["status"] == "created"


# ---------------------------------------------------------------------------
# Integration with _merge_into_event
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_merge_into_event_binds_attachments():
    """合併到既有事件時，attachment_ids 應綁到新建的 Report（而非事件）。"""
    from app.api.chat import _process_tool_use

    unbound = _attachment(report_id=None)
    target = MagicMock()
    target.id = uuid.uuid4()
    target.title = "既有火災事件"
    target.description = "原有描述"
    target.location_text = "台北市信義區市府路45號"
    target.severity = 3
    target.report_count = 1
    target.status = "reported"
    target.casualties = 0
    target.injured = 0
    target.trapped = 0
    target.occurred_at = datetime.now(timezone.utc)
    target.updated_at = datetime.now(timezone.utc)

    mock_db = _mock_db_with_attachments([unbound])
    mock_db.get.return_value = target

    captured_reports = []

    def _add(obj):
        from app.models.disaster_report import DisasterReport

        if isinstance(obj, DisasterReport):
            obj.id = uuid.uuid4()
            captured_reports.append(obj)

    mock_db.add.side_effect = _add

    with (
        patch(
            "app.api.chat.merge_event_descriptions",
            new_callable=AsyncMock,
            return_value="合併後描述",
        ),
        patch(
            "app.api.chat.reextract_numbers_from_description",
            new_callable=AsyncMock,
            return_value={},
        ),
    ):
        result = await _process_tool_use(
            _tool_data(merge_event_id=str(target.id)),
            "原始訊息",
            mock_db,
            _coords(),
            attachment_ids=[str(unbound.id)],
        )

    assert result["status"] == "merged"
    assert len(captured_reports) == 1
    assert unbound.report_id == captured_reports[0].id
