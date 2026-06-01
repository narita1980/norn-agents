"""DB アクセス。コミットは呼び出し側（route / background task）が制御する。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.orm import aliased

from norn.agents.schemas import AgentTurn, UserLevel
from norn.db.models import (
    AgentConversation,
    AgentMemory,
    ChatMessage,
    LearnerProfile,
    ReviewSession,
)

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
    user_level: UserLevel = "junior",
) -> ReviewSession:
    """`(repo, pr_number, user_level)` で冪等。既存があれば返し、なければ新規作成。

    `chat_thread_id` を None で渡すと UUID v4 を採番する。
    Phase 4 以降は HITL を前提とし、新規作成時のデフォルト status は
    `pending_approval`（若手の Start/Skip 待ち）。
    """

    stmt = select(ReviewSession).where(
        ReviewSession.repository_name == repository_name,
        ReviewSession.pr_number == pr_number,
        ReviewSession.user_level == user_level,
    )
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        return existing

    row = ReviewSession(
        id=str(uuid4()),
        repository_name=repository_name,
        pr_number=pr_number,
        user_level=user_level,
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
    user_level: UserLevel = "junior",
) -> ReviewSession | None:
    stmt = select(ReviewSession).where(
        ReviewSession.repository_name == repository_name,
        ReviewSession.pr_number == pr_number,
        ReviewSession.user_level == user_level,
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
    user_level: UserLevel = "junior",
) -> ChatMessage:
    row = ChatMessage(
        message_id=message_id or str(uuid4()),
        thread_id=thread_id,
        role=role,
        content=content,
        consensus_json=consensus,
        transcript_json=transcript,
        action_payload=action_payload,
        user_level=user_level,
    )
    session.add(row)
    await session.flush()
    return row


async def clear_approval_action_payload(
    session: AsyncSession,
    *,
    thread_id: str,
    session_id: str,
) -> None:
    """Start/Skip 後に HITL バナーを再表示しないよう action_payload を消す。"""
    stmt = select(ChatMessage).where(
        ChatMessage.thread_id == thread_id,
        ChatMessage.action_payload.isnot(None),
    )
    rows = (await session.execute(stmt)).scalars().all()
    for row in rows:
        payload = row.action_payload
        if isinstance(payload, dict) and payload.get("session_id") == session_id:
            row.action_payload = None


async def count_thread_messages(session: AsyncSession, thread_id: str) -> int:
    stmt = (
        select(func.count())
        .select_from(ChatMessage)
        .where(ChatMessage.thread_id == thread_id)
    )
    return int((await session.execute(stmt)).scalar_one())


async def get_thread_user_level(session: AsyncSession, thread_id: str) -> UserLevel | None:
    stmt = (
        select(ChatMessage.user_level)
        .where(ChatMessage.thread_id == thread_id)
        .order_by(ChatMessage.id.asc())
        .limit(1)
    )
    level = (await session.execute(stmt)).scalar_one_or_none()
    if level in {"junior", "mid", "senior"}:
        return level
    return None


async def load_thread_messages(
    session: AsyncSession, thread_id: str, *, user_level: UserLevel
) -> list[ChatMessage]:
    owner = await get_thread_user_level(session, thread_id)
    if owner is None or owner != user_level:
        return []
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
    session: AsyncSession, *, user_level: UserLevel, limit: int = 50
) -> list[ThreadSummary]:
    """thread_id 単位で集約。`user_level` が一致するスレッドのみ返す。"""

    first_msg_subq = (
        select(
            ChatMessage.thread_id.label("thread_id"),
            func.min(ChatMessage.id).label("first_id"),
        )
        .group_by(ChatMessage.thread_id)
        .subquery()
    )
    FirstMsg = aliased(ChatMessage)

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
        .join(first_msg_subq, ChatMessage.thread_id == first_msg_subq.c.thread_id)
        .join(FirstMsg, FirstMsg.id == first_msg_subq.c.first_id)
        .where(FirstMsg.user_level == user_level)
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


async def get_review_status_for_thread(
    session: AsyncSession, thread_id: str
) -> str | None:
    """thread_id に紐づく ReviewSession.status。レビュー未連携なら None。"""

    stmt = select(ReviewSession.status).where(ReviewSession.chat_thread_id == thread_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def delete_thread_by_id(
    session: AsyncSession, thread_id: str, *, user_level: UserLevel
) -> bool:
    """thread_id に紐づく ChatMessage と ReviewSession（あれば）を削除する。"""

    owner = await get_thread_user_level(session, thread_id)
    if owner is None or owner != user_level:
        return False

    review_stmt = select(ReviewSession).where(ReviewSession.chat_thread_id == thread_id)
    review_session = (await session.execute(review_stmt)).scalar_one_or_none()

    msg_result = await session.execute(
        delete(ChatMessage).where(ChatMessage.thread_id == thread_id)
    )
    messages_deleted = msg_result.rowcount or 0

    if review_session is not None:
        await session.delete(review_session)

    return messages_deleted > 0 or review_session is not None


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


async def recent_completed_sessions(session: AsyncSession, limit: int = 10) -> list[ReviewSession]:
    stmt = (
        select(ReviewSession)
        .where(ReviewSession.status == "completed")
        .order_by(ReviewSession.updated_at.desc())
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())


async def get_or_create_learner_profile(
    session: AsyncSession,
    user_id: int,
    *,
    skill_level: UserLevel = "junior",
) -> LearnerProfile:
    stmt = select(LearnerProfile).where(LearnerProfile.user_id == user_id)
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        return existing
    row = LearnerProfile(
        user_id=user_id,
        skill_level=skill_level,
        active_goals=[],
        resolved_topics=[],
        weak_areas=[],
    )
    session.add(row)
    await session.flush()
    return row


async def get_learner_profile(
    session: AsyncSession, user_id: int
) -> LearnerProfile | None:
    stmt = select(LearnerProfile).where(LearnerProfile.user_id == user_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def update_learner_profile(
    session: AsyncSession,
    user_id: int,
    *,
    skill_level: UserLevel,
    growth_summary: str,
    active_goals: list[str],
    resolved_topics: list[str],
    weak_areas: list[str],
    review_count: int,
) -> None:
    profile = await get_or_create_learner_profile(session, user_id, skill_level=skill_level)
    profile.skill_level = skill_level
    profile.growth_summary = growth_summary
    profile.active_goals = active_goals
    profile.resolved_topics = resolved_topics
    profile.weak_areas = weak_areas
    profile.review_count = review_count
    await session.flush()


async def append_agent_memory(
    session: AsyncSession,
    *,
    agent_name: str,
    scope: str,
    user_id: int | None,
    memory_type: str,
    content: str,
    source_session_id: str | None = None,
    quality_score: float = 1.0,
) -> AgentMemory:
    row = AgentMemory(
        agent_name=agent_name,
        scope=scope,
        user_id=user_id,
        memory_type=memory_type,
        content=content[:500],
        source_session_id=source_session_id,
        quality_score=quality_score,
    )
    session.add(row)
    await session.flush()
    return row


async def list_agent_memories(
    session: AsyncSession,
    *,
    agent_name: str,
    user_id: int | None,
    scope: str,
    limit: int = 5,
) -> list[AgentMemory]:
    stmt = (
        select(AgentMemory)
        .where(
            AgentMemory.agent_name == agent_name,
            AgentMemory.scope == scope,
        )
        .order_by(AgentMemory.quality_score.desc(), AgentMemory.created_at.desc())
        .limit(limit)
    )
    if scope == "user" and user_id is not None:
        stmt = stmt.where(AgentMemory.user_id == user_id)
    elif scope == "global":
        stmt = stmt.where(AgentMemory.user_id.is_(None))
    return list((await session.execute(stmt)).scalars().all())


_MAX_USER_MEMORIES_PER_AGENT = 8
_MAX_GLOBAL_MEMORIES_PER_AGENT = 5


async def prune_agent_memories(session: AsyncSession, *, user_id: int) -> None:
    for agent in ("urd", "verdandi", "skuld"):
        for scope, max_count, uid in (
            ("user", _MAX_USER_MEMORIES_PER_AGENT, user_id),
            ("global", _MAX_GLOBAL_MEMORIES_PER_AGENT, None),
        ):
            stmt = (
                select(AgentMemory)
                .where(AgentMemory.agent_name == agent, AgentMemory.scope == scope)
                .order_by(AgentMemory.quality_score.desc(), AgentMemory.created_at.desc())
            )
            if scope == "user":
                stmt = stmt.where(AgentMemory.user_id == uid)
            else:
                stmt = stmt.where(AgentMemory.user_id.is_(None))
            rows = list((await session.execute(stmt)).scalars().all())
            for row in rows[max_count:]:
                await session.delete(row)
    await session.flush()


async def update_message_feedback(
    session: AsyncSession,
    *,
    message_id: str,
    rating: int,
    user_level: UserLevel,
) -> bool:
    stmt = select(ChatMessage).where(ChatMessage.message_id == message_id)
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None or row.user_level != user_level:
        return False
    row.feedback_rating = rating
    await session.flush()
    return True


async def adjust_agent_memory_quality(
    session: AsyncSession,
    *,
    message_id: str,
    rating: int,
    user_level: UserLevel,
) -> None:
    """フィードバックに応じて関連 agent_memories の quality_score を調整。"""
    stmt = select(ChatMessage).where(ChatMessage.message_id == message_id)
    msg = (await session.execute(stmt)).scalar_one_or_none()
    if msg is None or msg.user_level != user_level:
        return
    thread_stmt = select(ReviewSession).where(ReviewSession.chat_thread_id == msg.thread_id)
    review = (await session.execute(thread_stmt)).scalar_one_or_none()
    session_id = review.id if review else None
    if session_id is None:
        return
    mem_stmt = select(AgentMemory).where(AgentMemory.source_session_id == session_id)
    memories = list((await session.execute(mem_stmt)).scalars().all())
    delta = 0.2 if rating > 0 else -0.3
    for mem in memories:
        mem.quality_score = max(0.1, min(2.0, mem.quality_score + delta))
    await session.flush()


async def list_growth_timeline(
    session: AsyncSession,
    user_id: int,
    *,
    limit: int = 20,
) -> list[dict[str, str | None]]:
    from norn.db.models import User

    user_row = await session.get(User, user_id)
    if user_row is None or user_row.user_level is None:
        return []

    user_level = user_row.user_level
    stmt = (
        select(ChatMessage)
        .where(
            ChatMessage.user_level == user_level,
            ChatMessage.role == "assistant",
            ChatMessage.consensus_json.isnot(None),
        )
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
    )
    rows = list((await session.execute(stmt)).scalars().all())
    timeline: list[dict[str, str | None]] = []
    for row in rows:
        consensus = row.consensus_json if isinstance(row.consensus_json, dict) else {}
        timeline.append(
            {
                "message_id": row.message_id,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "growth": str(consensus.get("growth") or ""),
                "summary": str(consensus.get("summary") or "")[:200],
                "tone": str(consensus.get("tone") or ""),
            }
        )
    return timeline


async def load_thread_chat_pairs(
    session: AsyncSession, thread_id: str, *, user_level: UserLevel
) -> list[tuple[str, str]]:
    rows = await load_thread_messages(session, thread_id, user_level=user_level)
    return [(r.role, r.content) for r in rows]
