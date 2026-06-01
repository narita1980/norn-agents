"""users.user_level 列追加（テストユーザー連携）

Revision ID: 0006_user_level_on_users
Revises: 0005_users
Create Date: 2026-06-01 00:00:00.000000

"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0006_user_level_on_users"
down_revision: str | None = "0005_users"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("user_level", sa.String(length=16), nullable=True))
    op.create_index("ix_users_user_level", "users", ["user_level"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_user_level", table_name="users")
    op.drop_column("users", "user_level")
