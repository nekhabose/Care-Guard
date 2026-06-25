import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base
from security.sqlalchemy_types import EncryptedText


class OutreachSession(Base):
    __tablename__ = "outreach_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), nullable=False, index=True)
    discharge_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("discharges.id"), nullable=False, index=True)

    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    channel: Mapped[str] = mapped_column(String, nullable=False)           # voice | sms
    # scheduled | in_progress | completed | failed | no_answer
    status: Mapped[str] = mapped_column(String, nullable=False, default="scheduled")
    outreach_number: Mapped[int] = mapped_column(Integer, nullable=False)  # 1..5

    twilio_call_sid: Mapped[str | None] = mapped_column(String)
    recording_s3_key: Mapped[str | None] = mapped_column(String)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    discharge: Mapped["Discharge"] = relationship(back_populates="sessions")
    turns: Mapped[list["ConversationTurn"]] = relationship(back_populates="session", lazy="selectin")
    escalations: Mapped[list["Escalation"]] = relationship(back_populates="session", lazy="selectin")


class ConversationTurn(Base):
    __tablename__ = "conversation_turns"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("outreach_sessions.id"), nullable=False, index=True)

    role: Mapped[str] = mapped_column(String, nullable=False)   # agent | patient
    # PHI — spoken patient content; encrypted at rest.
    content: Mapped[str] = mapped_column(EncryptedText, nullable=False)
    tool_calls: Mapped[dict | None] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped["OutreachSession"] = relationship(back_populates="turns")
