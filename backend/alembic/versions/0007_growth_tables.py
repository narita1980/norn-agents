"""成長機能: learner_profiles, agent_memories, learning_resources, users.github_username

Revision ID: 0007_growth_tables
Revises: 0006_user_level_on_users
Create Date: 2026-06-01 12:00:00.000000

"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0007_growth_tables"
down_revision: str | None = "0006_user_level_on_users"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("github_username", sa.String(length=128), nullable=True))
    op.add_column("chat_messages", sa.Column("feedback_rating", sa.Integer(), nullable=True))

    op.create_table(
        "learner_profiles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("skill_level", sa.String(length=16), server_default="junior", nullable=False),
        sa.Column("growth_summary", sa.Text(), server_default="", nullable=False),
        sa.Column("active_goals", sa.JSON(), nullable=True),
        sa.Column("resolved_topics", sa.JSON(), nullable=True),
        sa.Column("weak_areas", sa.JSON(), nullable=True),
        sa.Column("review_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_learner_profiles_user_id", "learner_profiles", ["user_id"], unique=True)

    op.create_table(
        "agent_memories",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("agent_name", sa.String(length=64), nullable=False),
        sa.Column("scope", sa.String(length=16), server_default="user", nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("memory_type", sa.String(length=32), server_default="pattern", nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("quality_score", sa.Float(), server_default="1.0", nullable=False),
        sa.Column("source_session_id", sa.String(length=36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_memories_agent_scope", "agent_memories", ["agent_name", "scope"])
    op.create_index("ix_agent_memories_user_id", "agent_memories", ["user_id"])

    op.create_table(
        "learning_resources",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("url", sa.String(length=512), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("tags", sa.String(length=255), server_default="", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("learning_resources")
    op.drop_index("ix_agent_memories_user_id", table_name="agent_memories")
    op.drop_index("ix_agent_memories_agent_scope", table_name="agent_memories")
    op.drop_table("agent_memories")
    op.drop_index("ix_learner_profiles_user_id", table_name="learner_profiles")
    op.drop_table("learner_profiles")
    op.drop_column("chat_messages", "feedback_rating")
    op.drop_column("users", "github_username")
