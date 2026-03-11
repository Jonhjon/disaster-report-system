import uuid
from datetime import datetime, timezone

from geoalchemy2 import Geometry
from sqlalchemy import CheckConstraint, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DisasterEvent(Base):
    __tablename__ = "disaster_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    disaster_type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    location_text: Mapped[str] = mapped_column(String(500), nullable=False)
    location = mapped_column(Geometry("POINT", srid=4326), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    casualties: Mapped[int] = mapped_column(Integer, default=0)
    injured: Mapped[int] = mapped_column(Integer, default=0)
    trapped: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="active")
    report_count: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    reports = relationship("DisasterReport", back_populates="event")

    __table_args__ = (
        CheckConstraint("severity >= 1 AND severity <= 5", name="ck_severity_range"),
        CheckConstraint(
            "status IN ('active', 'monitoring', 'resolved')", name="ck_status_values"
        ),
        Index("idx_events_location", "location", postgresql_using="gist"),
        Index("idx_events_disaster_type", "disaster_type"),
        Index("idx_events_status", "status"),
        Index("idx_events_occurred_at", "occurred_at"),
        Index("idx_events_severity", "severity"),
    )
