"""Semantic Kernel AgentGroupChat による合議（レガシー）。

並行合議（urd ∥ skuld → verdandi）は NornOrchestrator._run_deliberative_parallel に移行済み。
本モジュールは A/B ドキュメント参照用に残置。新規コードからは import しないこと。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from typing import Any

    from norn.agents.schemas import AgentTurn
    from norn.config import Settings

    EventCallback = Callable[[dict[str, Any]], Awaitable[None]]


async def run_deliberation_group_chat(
    *,
    initial_user_prompt: str,
    settings: Settings,
    on_event: EventCallback | None = None,
    prior_turns: list[AgentTurn] | None = None,
) -> list[AgentTurn]:
    raise RuntimeError(
        "run_deliberation_group_chat is deprecated; use NornOrchestrator parallel deliberation"
    )
