"""ReviewContext に成長コンテキストを載せるヘルパー。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from norn.agents.growth import build_growth_context, render_chat_history
from norn.agents.schemas import AgentTurn, ReviewContext, UserLevel
from norn.db.repositories import load_thread_chat_pairs

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def enrich_review_context(
    session: AsyncSession,
    context: ReviewContext,
    *,
    user_id: int | None,
    thread_id: str | None = None,
) -> ReviewContext:
    growth = await build_growth_context(session, user_id=user_id, user_level=context.user_level)

    chat_history = context.chat_history
    if thread_id and not context.is_pr_context:
        pairs = await load_thread_chat_pairs(session, thread_id, user_level=context.user_level)
        chat_history = render_chat_history(pairs, exclude_last=True)

    return context.model_copy(
        update={
            "user_id": user_id,
            "user_level": growth.skill_level,
            "learner_history": growth.learner_history,
            "agent_memories": growth.agent_memories,
            "learning_resources": growth.learning_resources,
            "chat_history": chat_history,
        }
    )


async def build_chat_review_context(
    session: AsyncSession,
    *,
    content: str,
    user_level: UserLevel,
    user_id: int | None,
    thread_id: str,
    prior_turns: list[AgentTurn] | None = None,
) -> ReviewContext:
    base = ReviewContext.from_user_input(content, user_level=user_level, prior_turns=prior_turns)
    return await enrich_review_context(session, base, user_id=user_id, thread_id=thread_id)
