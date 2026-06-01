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
    user_level: Mapped[str | None] = mapped_column(String(16), unique=True, nullable=True)
    github_username: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    learner_profile: Mapped[LearnerProfile | None] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )


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
    feedback_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LearnerProfile(Base):
    """若手エンジニアの成長プロファイル。users と 1:1。"""

    __tablename__ = "learner_profiles"
    __table_args__ = (Index("ix_learner_profiles_user_id", "user_id", unique=True),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    skill_level: Mapped[str] = mapped_column(String(16), default="junior", server_default="junior")
    growth_summary: Mapped[str] = mapped_column(Text, default="", server_default="")
    active_goals: Mapped[list[Any]] = mapped_column(JSON, default=list)
    resolved_topics: Mapped[list[Any]] = mapped_column(JSON, default=list)
    weak_areas: Mapped[list[Any]] = mapped_column(JSON, default=list)
    review_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="learner_profile")


class AgentMemory(Base):
    """女神エージェントの学習メモリ。scope=global は組織横断、user は若手固有。"""

    __tablename__ = "agent_memories"
    __table_args__ = (
        Index("ix_agent_memories_agent_scope", "agent_name", "scope"),
        Index("ix_agent_memories_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_name: Mapped[str] = mapped_column(String(64))
    scope: Mapped[str] = mapped_column(String(16), default="user")
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    memory_type: Mapped[str] = mapped_column(String(32), default="pattern")
    content: Mapped[str] = mapped_column(Text)
    quality_score: Mapped[float] = mapped_column(default=1.0)
    source_session_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LearningResource(Base):
    """Skuld RAG 用の学習リソースカタログ（Phase 5.7 スタブ）。"""

    __tablename__ = "learning_resources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(String(512))
    description: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
