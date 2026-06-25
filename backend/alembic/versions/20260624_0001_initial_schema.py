"""initial schema — baseline of all CareGuard tables

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-06-24

Baseline migration for the move from ``Base.metadata.create_all`` to Alembic-owned
schema. Mirrors the ORM models as of this revision, **excluding** ``call_opt_out``
(added in 0002) so existing databases built by ``create_all`` line up with this
baseline historically.

Each table is created only if absent, so this is safe to run against a database
that ``create_all`` already populated — those deployments can simply
``alembic upgrade head`` (the baseline no-ops, 0002 adds the new column) instead
of stamping. Fresh databases get the full schema here.

PHI columns are plain ``VARCHAR``/``TEXT`` at the database layer — application-layer
encryption (``EncryptedString``/``EncryptedText``) is transparent to the schema.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NOW = sa.text("now()")


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if not _has_table("patients"):
        op.create_table(
            "patients",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("epic_patient_id", sa.String(), nullable=False),
            sa.Column("mrn", sa.String(), nullable=True),
            sa.Column("first_name_enc", sa.String(), nullable=False),
            sa.Column("last_name_enc", sa.String(), nullable=False),
            sa.Column("phone_enc", sa.String(), nullable=False),
            sa.Column("date_of_birth", sa.Date(), nullable=True),
            sa.Column("risk_score", sa.Integer(), nullable=True),
            sa.Column("risk_level", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        )
        op.create_index("ix_patients_epic_patient_id", "patients", ["epic_patient_id"], unique=True)

    if not _has_table("discharges"):
        op.create_table(
            "discharges",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("patient_id", postgresql.UUID(as_uuid=True),
                      sa.ForeignKey("patients.id"), nullable=False),
            sa.Column("discharge_date", sa.Date(), nullable=False),
            sa.Column("hospital_name", sa.String(), nullable=False),
            sa.Column("primary_diagnosis_code", sa.String(), nullable=True),
            sa.Column("primary_diagnosis_name", sa.String(), nullable=True),
            sa.Column("hrrp_condition", sa.String(), nullable=True),
            sa.Column("discharge_summary_s3_key", sa.String(), nullable=True),
            sa.Column("medications", postgresql.JSONB(), nullable=True),
            sa.Column("followup_appointments", postgresql.JSONB(), nullable=True),
            sa.Column("discharge_instructions", sa.Text(), nullable=True),
            sa.Column("instructions_summary", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        )
        op.create_index("ix_discharges_patient_id", "discharges", ["patient_id"])
        op.create_index("ix_discharges_hrrp_condition", "discharges", ["hrrp_condition"])

    if not _has_table("outreach_sessions"):
        op.create_table(
            "outreach_sessions",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("patient_id", postgresql.UUID(as_uuid=True),
                      sa.ForeignKey("patients.id"), nullable=False),
            sa.Column("discharge_id", postgresql.UUID(as_uuid=True),
                      sa.ForeignKey("discharges.id"), nullable=False),
            sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("channel", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("outreach_number", sa.Integer(), nullable=False),
            sa.Column("twilio_call_sid", sa.String(), nullable=True),
            sa.Column("recording_s3_key", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        )
        op.create_index("ix_outreach_sessions_patient_id", "outreach_sessions", ["patient_id"])
        op.create_index("ix_outreach_sessions_discharge_id", "outreach_sessions", ["discharge_id"])

    if not _has_table("conversation_turns"):
        op.create_table(
            "conversation_turns",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("session_id", postgresql.UUID(as_uuid=True),
                      sa.ForeignKey("outreach_sessions.id"), nullable=False),
            sa.Column("role", sa.String(), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("tool_calls", postgresql.JSONB(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        )
        op.create_index("ix_conversation_turns_session_id", "conversation_turns", ["session_id"])

    if not _has_table("escalations"):
        op.create_table(
            "escalations",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("session_id", postgresql.UUID(as_uuid=True),
                      sa.ForeignKey("outreach_sessions.id"), nullable=False),
            sa.Column("patient_id", postgresql.UUID(as_uuid=True),
                      sa.ForeignKey("patients.id"), nullable=False),
            sa.Column("severity", sa.String(), nullable=False),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("symptoms_flagged", postgresql.JSONB(), nullable=True),
            sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("resolved_by", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        )
        op.create_index("ix_escalations_session_id", "escalations", ["session_id"])
        op.create_index("ix_escalations_patient_id", "escalations", ["patient_id"])


def downgrade() -> None:
    # Reverse dependency order.
    for table in ("escalations", "conversation_turns", "outreach_sessions", "discharges", "patients"):
        if _has_table(table):
            op.drop_table(table)
