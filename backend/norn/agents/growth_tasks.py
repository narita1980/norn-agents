"""合議後の成長記録を非同期で実行するヘルパー。"""

from __future__ import annotations

import logging

from norn.agents.growth import PostSessionReflector
from norn.agents.llm import AzureLLMClient
from norn.agents.schemas import AgentTurn, ConsensusOutput, UserLevel
from norn.config import get_settings
from norn.db import session_scope
from norn.db.users import resolve_user_id

logger = logging.getLogger("norn.agents.growth_tasks")


async def run_post_session_reflection(
    *,
    user_level: UserLevel,
    user_id: int | None = None,
    consensus: ConsensusOutput | None,
    transcript: list[AgentTurn],
    user_input: str,
    source_session_id: str | None = None,
) -> None:
    settings = get_settings()
    llm = None
    if settings.llm_configured:
        try:
            llm = AzureLLMClient(settings)
        except Exception:
            logger.exception("LLM init failed for reflection")
    reflector = PostSessionReflector(llm=llm)
    async with session_scope() as session:
        resolved_user_id = user_id
        if resolved_user_id is None:
            resolved_user_id = await resolve_user_id(session, user_level)
        try:
            await reflector.reflect_and_persist(
                session,
                user_id=resolved_user_id,
                user_level=user_level,
                consensus=consensus,
                transcript=transcript,
                user_input=user_input,
                source_session_id=source_session_id,
            )
            await session.commit()
        except Exception:
            logger.exception("post-session reflection failed")
            await session.rollback()
