import pytest
from pydantic import ValidationError
from app.schemas.llm_tools import SubmitDisasterReportPayload


VALID_PAYLOAD: dict = {
    "disaster_type": "flooding",
    "description": "台北市信義區仁愛路四段發生嚴重淹水，積水約50公分",
    "location_text": "台北市信義區仁愛路四段",
    "severity": 3,
    "casualties": 0,
    "injured": 2,
    "trapped": 1,
    "reporter_name": "王小明",
    "reporter_phone": "0912345678",
}


def test_valid_payload_parses():
    obj = SubmitDisasterReportPayload.model_validate(VALID_PAYLOAD)
    assert obj.disaster_type == "flooding"
    assert obj.severity == 3
    assert obj.casualties == 0
    assert obj.trapped == 1
    assert obj.occurred_at is None
    assert obj.merge_event_id is None


def test_optional_fields_default_to_zero_or_none():
    minimal = {k: v for k, v in VALID_PAYLOAD.items()
               if k not in ("casualties", "injured", "trapped", "occurred_at")}
    obj = SubmitDisasterReportPayload.model_validate(minimal)
    assert obj.casualties == 0
    assert obj.injured == 0
    assert obj.trapped == 0
    assert obj.occurred_at is None


def test_severity_below_range_fails():
    bad = {**VALID_PAYLOAD, "severity": 0}
    with pytest.raises(ValidationError):
        SubmitDisasterReportPayload.model_validate(bad)


def test_severity_above_range_fails():
    bad = {**VALID_PAYLOAD, "severity": 6}
    with pytest.raises(ValidationError):
        SubmitDisasterReportPayload.model_validate(bad)


def test_invalid_disaster_type_fails():
    bad = {**VALID_PAYLOAD, "disaster_type": "meteor_strike"}
    with pytest.raises(ValidationError):
        SubmitDisasterReportPayload.model_validate(bad)


def test_negative_casualties_fails():
    bad = {**VALID_PAYLOAD, "casualties": -1}
    with pytest.raises(ValidationError):
        SubmitDisasterReportPayload.model_validate(bad)


def test_extra_fields_are_ignored():
    extra = {**VALID_PAYLOAD, "unknown_field": "should_be_ignored"}
    obj = SubmitDisasterReportPayload.model_validate(extra)
    assert not hasattr(obj, "unknown_field")


def test_merge_event_id_accepted():
    with_merge = {**VALID_PAYLOAD, "merge_event_id": "new"}
    obj = SubmitDisasterReportPayload.model_validate(with_merge)
    assert obj.merge_event_id == "new"


def test_all_disaster_types_valid():
    types = ["trapped", "road_collapse", "flooding", "landslide",
             "small_landslide", "building_damage", "utility_damage", "fire", "other"]
    for t in types:
        obj = SubmitDisasterReportPayload.model_validate({**VALID_PAYLOAD, "disaster_type": t})
        assert obj.disaster_type == t
