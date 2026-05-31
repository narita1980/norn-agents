"""SQLAlchemy 2.x モデル定義。

スキーマは Postgres 互換を保つため、JSON / DateTime(timezone=True) / String(36) UUID を使う。
users テーブルはログイン認証用（ID / パスワードは DB 管理）。
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 — required at runtime by SQLAlchemy Mapped[datetime]
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """SQLAlchemy 全モデルのベース。"""


class User(Base):
    """ログイン用ユーザー。パスワードは bcrypt ハッシュのみ保存。"""

    __tablename__ = "users"
    __table_args__ = (Index("ix_users_username", "username", unique=True),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReviewSession(Base):
    """1 つの Draft PR に対する合議セッション。チャット UI スレッドと 1:1。

    status は文字列で `pending_approval` / `running` / `completed` / `failed` / `skipped` を取る。
    enum 制約はかけず、コード側で扱う（マイグレーション無しで値を増やせる柔軟性のため）。
    """

    __tablename__ = "review_sessions"
    __table_args__ = (
        UniqueConstraint(
            "repository_name",
            "pr_number",
            "user_level",
            name="uq_review_sessions_repo_pr_level",
        ),
        Index("ix_review_sessions_chat_thread_id", "chat_thread_id", unique=True),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    repository_name: Mapped[str] = mapped_column(String(255))
    pr_number: Mapped[int] = mapped_column(Integer)
    user_level: Mapped[str] = mapped_column(String(16), default="junior", server_default="junior")
    chat_thread_id: Mapped[str] = mapped_column(String(36))
    status: Mapped[str] = mapped_column(String(32), default="running")
    # HITL で /reviews/{id}/start を受けたとき再生する webhook payload。
    payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    conversations: Mapped[list[AgentConversation]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="AgentConversation.id"
    )


class AgentConversation(Base):
    """合議中の 1 ターン分の永続化レコード。"""

    __tablename__ = "agent_conversations"
    __table_args__ = (Index("ix_agent_conversations_session", "session_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("review_sessions.id", ondelete="CASCADE")
    )
    agent_name: Mapped[str] = mapped_column(String(64))
    role_label: Mapped[str] = mapped_column(String(128))
    message_content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped[ReviewSession] = relationship(back_populates="conversations")


class ChatMessage(Base):
    """チャット UI の 1 メッセージ。user / assistant のいずれか。"""

    __tablename__ = "chat_messages"
    __table_args__ = (Index("ix_chat_messages_thread_id", "thread_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message_id: Mapped[str] = mapped_column(String(36), unique=True)
    thread_id: Mapped[str] = mapped_column(String(36))
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    consensus_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    transcript_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    # HITL の Start/Skip ボタンなど、フロントが解釈する構造化アクション。
    action_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    user_level: Mapped[str] = mapped_column(String(16), default="junior", server_default="junior")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
