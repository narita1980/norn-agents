"""chat_messages.user_level カラム追加

Revision ID: 0003_chat_user_level
Revises: 0002_phase4_columns
Create Date: 2026-05-31 12:00:00.000000

"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0003_chat_user_level"
down_revision: str | None = "0002_phase4_columns"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "chat_messages",
        sa.Column("user_level", sa.String(length=16), nullable=False, server_default="junior"),
    )
    op.create_index("ix_chat_messages_user_level", "chat_messages", ["user_level"])


def downgrade() -> None:
    op.drop_index("ix_chat_messages_user_level", table_name="chat_messages")
    op.drop_column("chat_messages", "user_level")
