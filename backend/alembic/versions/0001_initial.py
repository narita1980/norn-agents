"""initial schema: review_sessions, agent_conversations, chat_messages

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-31 00:00:00.000000

"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "review_sessions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("repository_name", sa.String(length=255), nullable=False),
        sa.Column("pr_number", sa.Integer(), nullable=False),
        sa.Column("chat_thread_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="running"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("repository_name", "pr_number", name="uq_review_sessions_repo_pr"),
    )
    op.create_index(
        "ix_review_sessions_chat_thread_id",
        "review_sessions",
        ["chat_thread_id"],
        unique=True,
    )

    op.create_table(
        "agent_conversations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "session_id",
            sa.String(length=36),
            sa.ForeignKey("review_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("agent_name", sa.String(length=64), nullable=False),
        sa.Column("role_label", sa.String(length=128), nullable=False),
        sa.Column("message_content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_agent_conversations_session",
        "agent_conversations",
        ["session_id"],
    )

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("message_id", sa.String(length=36), nullable=False),
        sa.Column("thread_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("consensus_json", sa.JSON(), nullable=True),
        sa.Column("transcript_json", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("message_id", name="uq_chat_messages_message_id"),
    )
    op.create_index("ix_chat_messages_thread_id", "chat_messages", ["thread_id"])


def downgrade() -> None:
    op.drop_index("ix_chat_messages_thread_id", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("ix_agent_conversations_session", table_name="agent_conversations")
    op.drop_table("agent_conversations")
    op.drop_index("ix_review_sessions_chat_thread_id", table_name="review_sessions")
    op.drop_table("review_sessions")
