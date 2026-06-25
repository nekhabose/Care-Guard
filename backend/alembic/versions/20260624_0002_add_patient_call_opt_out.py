"""add patients.call_opt_out (Privacy Rule — outreach opt-out)

Revision ID: 0002_call_opt_out
Revises: 0001_initial_schema
Create Date: 2026-06-24

Adds the ``call_opt_out`` column to ``patients``. Existing rows default to
``false`` (callable) to preserve current behavior; the patient's recorded
preference then flips it via the contact-preferences endpoint.

Idempotent: a database that pre-dates Alembic adoption may already have had the
column added by ``create_all``. The upgrade checks for the column first so it is
safe to run in either order.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_call_opt_out"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return column in {col["name"] for col in inspector.get_columns(table)}


def upgrade() -> None:
    if _has_column("patients", "call_opt_out"):
        return
    op.add_column(
        "patients",
        sa.Column(
            "call_opt_out",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    if _has_column("patients", "call_opt_out"):
        op.drop_column("patients", "call_opt_out")
