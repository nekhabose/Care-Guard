import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base
from security.sqlalchemy_types import EncryptedString


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    epic_patient_id: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    mrn: Mapped[str | None] = mapped_column(String)

    # PHI — Fernet-encrypted at rest via EncryptedString. The ORM attribute holds
    # plaintext in memory; the column stores ciphertext. The `_enc` suffix marks
    # the protected fields; the properties below expose plaintext to API schemas.
    first_name_enc: Mapped[str] = mapped_column(EncryptedString, nullable=False)
    last_name_enc: Mapped[str] = mapped_column(EncryptedString, nullable=False)
    phone_enc: Mapped[str] = mapped_column(EncryptedString, nullable=False)

    @property
    def first_name(self) -> str:
        return self.first_name_enc

    @property
    def last_name(self) -> str:
        return self.last_name_enc

    @property
    def phone(self) -> str:
        return self.phone_enc

    date_of_birth: Mapped[date | None] = mapped_column(Date)
    risk_score: Mapped[int | None] = mapped_column(Integer)
    risk_level: Mapped[str | None] = mapped_column(String)  # high | medium | low

    # Privacy Rule — patient's right to opt out of automated outreach calls.
    call_opt_out: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    discharges: Mapped[list["Discharge"]] = relationship(back_populates="patient", lazy="selectin")
