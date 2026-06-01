"""review_sessions.user_level 追加と (repo, pr, user_level) 一意制約

Revision ID: 0004_review_session_user_level
Revises: 0003_chat_user_level
Create Date: 2026-05-31 14:00:00.000000

"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0004_review_session_user_level"
down_revision: str | None = "0003_chat_user_level"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("review_sessions")}

    with op.batch_alter_table("review_sessions", recreate="always") as batch_op:
        if "user_level" not in columns:
            batch_op.add_column(
                sa.Column(
                    "user_level", sa.String(length=16), nullable=False, server_default="junior"
                ),
            )
        batch_op.drop_constraint("uq_review_sessions_repo_pr", type_="unique")
        batch_op.create_unique_constraint(
            "uq_review_sessions_repo_pr_level",
            ["repository_name", "pr_number", "user_level"],
        )


def downgrade() -> None:
    with op.batch_alter_table("review_sessions", recreate="always") as batch_op:
        batch_op.drop_constraint("uq_review_sessions_repo_pr_level", type_="unique")
        batch_op.create_unique_constraint(
            "uq_review_sessions_repo_pr",
            ["repository_name", "pr_number"],
        )
        batch_op.drop_column("user_level")
