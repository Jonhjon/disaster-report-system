"""PostgreSQL integration coverage for statistics-specific SQL.

Run explicitly with ``RUN_POSTGRES_INTEGRATION=1``.  The guard below refuses
to connect unless the configured database name ends in ``_test``.
"""
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from geoalchemy2.elements import WKTElement
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app import database
from app.config import Settings
from app.models.disaster_event import DisasterEvent
from app.services.stats_service import get_statistics


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_INTEGRATION") != "1",
    reason="set RUN_POSTGRES_INTEGRATION=1 to run PostgreSQL integration tests",
)


def _test_database_url() -> str:
    env_file = Path(__file__).resolve().parents[1] / ".env.test"
    settings = Settings(_env_file=env_file)
    database_url = settings.DATABASE_URL
    database_name = make_url(database_url).database or ""
    if not database_name.endswith("_test"):
        pytest.fail("PostgreSQL integration tests require a database ending in _test")
    return database_url


def test_statistics_postgres_timezone_percentiles_and_snapshot_mode(monkeypatch):
    engine = create_engine(_test_database_url())
    marker = f"stats-integration-{uuid4()}"
    boundary_marker = f"stats-date-to-boundary-{uuid4()}"
    event_ids = []
    base = datetime(2026, 1, 1, 15, 30, tzinfo=timezone.utc)
    taipei = timezone(timedelta(hours=8))
    date_to = datetime(2026, 1, 3, tzinfo=taipei)

    try:
        with Session(engine) as setup_db:
            event_specs = [
                (
                    f"{marker}-{index}",
                    base + timedelta(hours=index),
                    base,
                    base + timedelta(hours=hours),
                )
                for index, hours in enumerate((2, 10, 48))
            ]
            event_specs.extend(
                [
                    (
                        f"{boundary_marker}-included",
                        date_to - timedelta(microseconds=1),
                        date_to - timedelta(microseconds=1),
                        date_to + timedelta(hours=1),
                    ),
                    (
                        f"{boundary_marker}-excluded",
                        date_to,
                        date_to,
                        date_to + timedelta(hours=1),
                    ),
                ]
            )
            for title, occurred_at, created_at, resolved_at in event_specs:
                event = DisasterEvent(
                    title=title,
                    disaster_type="fire",
                    severity=3,
                    location_text="integration-test",
                    location=WKTElement("POINT(121.565 25.033)", srid=4326),
                    occurred_at=occurred_at,
                    casualties=0,
                    injured=0,
                    severe_injured=0,
                    trapped=0,
                    status="resolved",
                    report_count=1,
                    location_approximate=False,
                    occurred_at_approximate=False,
                    created_at=created_at,
                    resolved_at=resolved_at,
                    updated_at=resolved_at,
                )
                setup_db.add(event)
                setup_db.flush()
                event_ids.append(event.id)
            setup_db.commit()

        monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=engine))
        statistics_dependency = database.get_statistics_db()
        try:
            stats_db = next(statistics_dependency)
            result = get_statistics(
                stats_db,
                search=marker,
                bucket="day",
                tz="Asia/Taipei",
            )

            assert result.summary.total_events == 3
            assert [
                (point.bucket_start.isoformat(), point.count)
                for point in result.trend
            ] == [("2026-01-01", 1), ("2026-01-02", 2)]
            assert result.resolution.avg_hours == 20.0
            assert result.resolution.median_hours == 10.0
            assert result.resolution.p90_hours == 40.4

            boundary_result = get_statistics(
                stats_db,
                search=boundary_marker,
                date_to=date_to,
                bucket="day",
                tz="Asia/Taipei",
            )
            assert boundary_result.summary.total_events == 1
            assert [
                (point.bucket_start.isoformat(), point.count)
                for point in boundary_result.trend
            ] == [("2026-01-02", 1)]

            assert (
                stats_db.execute(text("SHOW transaction_isolation")).scalar()
                == "repeatable read"
            )
            assert stats_db.execute(text("SHOW transaction_read_only")).scalar() == "on"
        finally:
            statistics_dependency.close()
    finally:
        with Session(engine) as cleanup_db:
            if event_ids:
                cleanup_db.query(DisasterEvent).filter(
                    DisasterEvent.id.in_(event_ids)
                ).delete(synchronize_session=False)
                cleanup_db.commit()
        engine.dispose()
