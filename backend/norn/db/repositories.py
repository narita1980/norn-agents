"""DB アクセス。コミットは呼び出し側（route / background task）が制御する。"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import select

from norn.agents.schemas import AgentTurn
from norn.db.models import AgentConversation, ChatMessage, ReviewSession

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def get_or_create_review_session(
    session: AsyncSession,
    *,
    repository_name: str,
    pr_number: int,
    chat_thread_id: str | None = None,
) -> ReviewSession:
    """`(repo, pr_number)` で冪等。既存があれば返し、なければ新規作成。

    `chat_thread_id` を None で渡すと UUID v4 を採番する。
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
        status="running",
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
) -> ChatMessage:
    row = ChatMessage(
        message_id=message_id or str(uuid4()),
        thread_id=thread_id,
        role=role,
        content=content,
        consensus_json=consensus,
        transcript_json=transcript,
    )
    session.add(row)
    await session.flush()
    return row


async def load_thread_messages(session: AsyncSession, thread_id: str) -> list[ChatMessage]:
    stmt = (
        select(ChatMessage).where(ChatMessage.thread_id == thread_id).order_by(ChatMessage.id.asc())
    )
    return list((await session.execute(stmt)).scalars().all())
