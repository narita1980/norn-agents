"""DB アクセス。コミットは呼び出し側（route / background task）が制御する。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy import func, select

from norn.agents.schemas import AgentTurn
from norn.db.models import AgentConversation, ChatMessage, ReviewSession

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession


async def get_or_create_review_session(
    session: AsyncSession,
    *,
    repository_name: str,
    pr_number: int,
    chat_thread_id: str | None = None,
    default_status: str = "pending_approval",
) -> ReviewSession:
    """`(repo, pr_number)` で冪等。既存があれば返し、なければ新規作成。

    `chat_thread_id` を None で渡すと UUID v4 を採番する。
    Phase 4 以降は HITL を前提とし、新規作成時のデフォルト status は
    `pending_approval`（若手の Start/Skip 待ち）。
    """

    stmt = select(ReviewSession).where(
        ReviewSession.repository_name == repository_name,
        ReviewSession.pr_number == pr_number,
    )
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        return existing

    row = ReviewSession(
        id=str(uuid4()),
        repository_name=repository_name,
        pr_number=pr_number,
        chat_thread_id=chat_thread_id or str(uuid4()),
        status=default_status,
    )
    session.add(row)
    await session.flush()
    return row


async def find_session_by_pr(
    session: AsyncSession,
    *,
    repository_name: str,
    pr_number: int,
) -> ReviewSession | None:
    stmt = select(ReviewSession).where(
        ReviewSession.repository_name == repository_name,
        ReviewSession.pr_number == pr_number,
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def mark_session_status(session: AsyncSession, session_id: str, status: str) -> None:
    row = await session.get(ReviewSession, session_id)
    if row is None:
        return
    row.status = status


async def set_session_payload(
    session: AsyncSession, session_id: str, payload: dict[str, Any]
) -> None:
    row = await session.get(ReviewSession, session_id)
    if row is None:
        return
    row.payload_json = payload


async def load_session(session: AsyncSession, session_id: str) -> ReviewSession | None:
    return await session.get(ReviewSession, session_id)


async def list_sessions(session: AsyncSession, limit: int = 50) -> list[ReviewSession]:
    stmt = select(ReviewSession).order_by(ReviewSession.updated_at.desc()).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def append_agent_turns(
    session: AsyncSession,
    session_id: str,
    turns: list[AgentTurn],
) -> None:
    for turn in turns:
        session.add(
            AgentConversation(
                session_id=session_id,
                agent_name=turn.agent,
                role_label=turn.role_label,
                message_content=turn.content,
            )
        )
    await session.flush()


async def load_prior_turns(session: AsyncSession, session_id: str) -> list[AgentTurn]:
    stmt = (
        select(AgentConversation)
        .where(AgentConversation.session_id == session_id)
        .order_by(AgentConversation.id.asc())
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [
        AgentTurn(agent=r.agent_name, role_label=r.role_label, content=r.message_content)
        for r in rows
    ]


async def append_chat_message(
    session: AsyncSession,
    *,
    thread_id: str,
    role: str,
    content: str,
    message_id: str | None = None,
    consensus: dict | None = None,
    transcript: list[dict] | None = None,
    action_payload: dict | None = None,
) -> ChatMessage:
    row = ChatMessage(
        message_id=message_id or str(uuid4()),
        thread_id=thread_id,
        role=role,
        content=content,
        consensus_json=consensus,
        transcript_json=transcript,
        action_payload=action_payload,
    )
    session.add(row)
    await session.flush()
    return row


async def load_thread_messages(session: AsyncSession, thread_id: str) -> list[ChatMessage]:
    stmt = (
        select(ChatMessage).where(ChatMessage.thread_id == thread_id).order_by(ChatMessage.id.asc())
    )
    return list((await session.execute(stmt)).scalars().all())


@dataclass(slots=True)
class ThreadSummary:
    """サイドバー一覧 1 件分。PR 由来かアドホックチャットかは session_id の有無で判定。"""

    thread_id: str
    last_message_at: datetime | None
    last_role: str | None
    last_excerpt: str
    session_id: str | None
    repository_name: str | None
    pr_number: int | None
    status: str | None
    has_pending_action: bool


async def list_thread_summaries(
    session: AsyncSession, limit: int = 50
) -> list[ThreadSummary]:
    """thread_id 単位で集約した最新メッセージ + 紐づく ReviewSession 情報。

    PR 経路では ReviewSession 1:1 chat_thread_id があり、アドホックチャット経路では
    ReviewSession が無い thread_id だけが残る。両方を最新更新順に並べる。
    """

    latest_id_subq = (
        select(
            ChatMessage.thread_id.label("thread_id"),
            func.max(ChatMessage.id).label("max_id"),
            func.max(ChatMessage.created_at).label("last_message_at"),
        )
        .group_by(ChatMessage.thread_id)
        .subquery()
    )
    stmt = (
        select(
            ChatMessage,
            latest_id_subq.c.last_message_at,
            ReviewSession.id,
            ReviewSession.repository_name,
            ReviewSession.pr_number,
            ReviewSession.status,
        )
        .join(
            latest_id_subq,
            (ChatMessage.id == latest_id_subq.c.max_id)
            & (ChatMessage.thread_id == latest_id_subq.c.thread_id),
        )
        .join(
            ReviewSession,
            ReviewSession.chat_thread_id == ChatMessage.thread_id,
            isouter=True,
        )
        .order_by(latest_id_subq.c.last_message_at.desc())
        .limit(limit)
    )
    rows = (await session.execute(stmt)).all()
    summaries: list[ThreadSummary] = []
    for msg, last_at, sess_id, repo, pr_num, status in rows:
        excerpt = (msg.content or "").strip().splitlines()[0] if msg.content else ""
        if len(excerpt) > 80:
            excerpt = excerpt[:80] + "…"
        summaries.append(
            ThreadSummary(
                thread_id=msg.thread_id,
                last_message_at=last_at,
                last_role=msg.role,
                last_excerpt=excerpt,
                session_id=sess_id,
                repository_name=repo,
                pr_number=pr_num,
                status=status,
                has_pending_action=bool(
                    msg.action_payload and msg.action_payload.get("type") == "start_or_skip"
                ),
            )
        )
    return summaries


@dataclass(slots=True)
class SessionStats:
    """ダッシュボード用に集約した数値。"""

    total: int
    by_status: dict[str, int]
    by_tone: dict[str, int]


async def aggregate_session_stats(session: AsyncSession) -> SessionStats:
    """ReviewSession の件数を status 別に、Moderator の tone を chat_messages から集約。"""

    status_stmt = select(ReviewSession.status, func.count()).group_by(ReviewSession.status)
    by_status: dict[str, int] = {}
    total = 0
    for status, count in (await session.execute(status_stmt)).all():
        by_status[status] = int(count)
        total += int(count)

    tone_stmt = select(ChatMessage.consensus_json).where(ChatMessage.consensus_json.is_not(None))
    by_tone: dict[str, int] = {}
    for (payload,) in (await session.execute(tone_stmt)).all():
        if not isinstance(payload, dict):
            continue
        tone = payload.get("tone")
        if not isinstance(tone, str):
            continue
        by_tone[tone] = by_tone.get(tone, 0) + 1

    return SessionStats(total=total, by_status=by_status, by_tone=by_tone)


async def recent_completed_sessions(
    session: AsyncSession, limit: int = 10
) -> list[ReviewSession]:
    stmt = (
        select(ReviewSession)
        .where(ReviewSession.status == "completed")
        .order_by(ReviewSession.updated_at.desc())
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())
