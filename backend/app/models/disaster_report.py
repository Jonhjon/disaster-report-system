import uuid
from datetime import datetime, timezone

from geoalchemy2 import Geometry
from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DisasterReport(Base):
    __tablename__ = "disaster_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("disaster_events.id"), nullable=True
    )
    reporter_name: Mapped[str | None] = mapped_column(String(100))
    reporter_phone: Mapped[str | None] = mapped_column(String(20))
    raw_message: Mapped[str] = mapped_column(Text, nullable=False)
    extracted_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    location = mapped_column(Geometry("POINT", srid=4326), nullable=True)
    location_text: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    event = relationship("DisasterEvent", back_populates="reports")

    __table_args__ = (
        Index("idx_reports_event_id", "event_id"),
        Index("idx_reports_location", "location", postgresql_using="gist"),
        Index("idx_reports_created_at", "created_at"),
    )
