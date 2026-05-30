"""phase 4: payload_json / action_payload columns

Revision ID: 0002_phase4_columns
Revises: 0001_initial
Create Date: 2026-05-31 04:00:00.000000

"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0002_phase4_columns"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "review_sessions",
        sa.Column("payload_json", sa.JSON(), nullable=True),
    )
    op.add_column(
        "chat_messages",
        sa.Column("action_payload", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("chat_messages", "action_payload")
    op.drop_column("review_sessions", "payload_json")
