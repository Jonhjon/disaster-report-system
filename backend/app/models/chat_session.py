import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_token: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4
    )
    event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("disaster_events.id", ondelete="SET NULL"),
        nullable=True,
    )
    report_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("disaster_reports.id", ondelete="SET NULL"),
        nullable=True,
    )
    messages: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    pending_questions: Mapped[list[dict]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    last_active_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    event = relationship("DisasterEvent")
    report = relationship("DisasterReport")
    clarification_requests = relationship(
        "ClarificationRequest", back_populates="session"
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'awaiting_user', 'closed')",
            name="ck_session_status",
        ),
        Index("idx_sessions_token", "session_token"),
        Index("idx_sessions_event", "event_id"),
    )
