"""Semantic Kernel AgentGroupChat による制約付き 3 女神合議。

固定順（urd → verdandi → skuld）を必須 3 ターンとして実行し、
必要時のみ Kernel 関数で追加 1 ターン（最大 2 ターン）を許可する。
モデレーター JSON 収束は NornOrchestrator._finalize_with_moderator に委譲。
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from semantic_kernel.agents import AgentGroupChat, ChatCompletionAgent
from semantic_kernel.agents.strategies.selection.selection_strategy import SelectionStrategy
from semantic_kernel.agents.strategies.termination.termination_strategy import TerminationStrategy
from semantic_kernel.contents.chat_message_content import ChatMessageContent
from semantic_kernel.contents.utils.author_role import AuthorRole
from semantic_kernel.functions import KernelFunctionFromPrompt
from semantic_kernel.kernel import Kernel  # noqa: TC002 — runtime AgentGroupChat

from norn.agents.llm import build_chat_kernel
from norn.agents.personas import SKULD, URD, VERDANDI, Persona
from norn.agents.schemas import AgentTurn

if TYPE_CHECKING:
    from norn.config import Settings

logger = logging.getLogger("norn.agents.sk_group_chat")

EventCallback = Callable[[dict[str, Any]], Awaitable[None]]

_DELIBERATIVE_PERSONAS: tuple[Persona, ...] = (URD, VERDANDI, SKULD)
_MANDATORY_ORDER: tuple[str, ...] = ("urd", "verdandi", "skuld")
_GODDESS_NAMES: frozenset[str] = frozenset(_MANDATORY_ORDER)

_EXTRA_SELECTION_PROMPT = """
あなたは Norn 合議の進行係です。ウルド・ヴェルダンディ・スクルドの必須 3 ターンは完了しました。

参加可能なエージェント名: {{$agents}}

直近の会話:
{{$history}}

追加の 1 ターンだけ、トーン調整や技術指摘のすり合わせが本当に必要な場合のみ、
次に発言すべきエージェント名を 1 つ返してください（urd / verdandi / skuld）。
不要なら done とだけ返してください。
""".strip()

_EXTRA_NEEDED_PROMPT = """
3 女神（urd, verdandi, skuld）が 1 回ずつ発言しました。

会話:
{{$history}}

ヴェルダンディとウルドの間で、トーンや must_fix の厳しさについて
追加 1 ターンのすり合わせが必要ですか？
必要なら yes、不要なら no とだけ答えてください。
""".strip()


def _agent_by_name(agents: list[ChatCompletionAgent], name: str) -> ChatCompletionAgent:
    for agent in agents:
        if agent.name == name:
            return agent
    raise ValueError(f"agent not found: {name}")


def _goddess_turn_count(history: list[ChatMessageContent]) -> int:
    return sum(
        1
        for msg in history
        if msg.role == AuthorRole.ASSISTANT and (msg.name or "") in _GODDESS_NAMES
    )


def _history_excerpt(history: list[ChatMessageContent], *, max_messages: int = 8) -> str:
    lines: list[str] = []
    for msg in history[-max_messages:]:
        role = msg.role.value if hasattr(msg.role, "value") else str(msg.role)
        author = msg.name or role
        body = (msg.content or "").strip()
        if len(body) > 800:
            body = body[:800] + "…"
        lines.append(f"[{author}] {body}")
    return "\n".join(lines) if lines else "（履歴なし）"


class NornDeliberationSelectionStrategy(SelectionStrategy):
    """必須 3 ターンは固定順。以降は Kernel 関数で追加 1 ターンの話者を選ぶ。"""

    kernel: Kernel
    extra_selection_function: Any
    _extra_agent_name: str | None = None

    async def select_agent(
        self,
        agents: list[Any],
        history: list[ChatMessageContent],
    ) -> Any:
        count = _goddess_turn_count(history)
        if count < len(_MANDATORY_ORDER):
            return _agent_by_name(agents, _MANDATORY_ORDER[count])

        if self._extra_agent_name is not None:
            return _agent_by_name(agents, self._extra_agent_name)

        agent_names = ", ".join(a.name for a in agents if a.name)
        result = await self.extra_selection_function.invoke(
            kernel=self.kernel,
            arguments={
                "agents": agent_names,
                "history": _history_excerpt(history),
            },
        )
        raw = str(result.value[0] if result.value else "done").strip().lower()
        choice = raw.split()[0] if raw else "done"
        if choice in _GODDESS_NAMES:
            self._extra_agent_name = choice
            logger.info("group_chat extra round selected agent=%s", choice)
            return _agent_by_name(agents, choice)

        logger.info("group_chat no extra round (selection=%s)", raw)
        return _agent_by_name(agents, "skuld")


class NornDeliberationTerminationStrategy(TerminationStrategy):
    """必須 3 ターン後に追加議論要否を判定。maximum_iterations で上限。"""

    kernel: Kernel
    extra_needed_function: Any
    maximum_iterations: int = 7

    async def should_agent_terminate(
        self,
        agent: Any,
        history: list[ChatMessageContent],
    ) -> bool:
        count = _goddess_turn_count(history)
        if count < 3:
            return False
        if count >= self.maximum_iterations:
            return True
        if count == 3:
            needs_extra = await self._needs_extra_discussion(history)
            return not needs_extra
        return True

    async def _needs_extra_discussion(self, history: list[ChatMessageContent]) -> bool:
        result = await self.extra_needed_function.invoke(
            kernel=self.kernel,
            arguments={"history": _history_excerpt(history)},
        )
        raw = str(result.value[0] if result.value else "no").strip().lower()
        return raw.startswith("y")


def _build_deliberation_agents(kernel: Kernel) -> list[ChatCompletionAgent]:
    return [
        ChatCompletionAgent(
            kernel=kernel,
            name=persona.name,
            instructions=persona.system_prompt,
        )
        for persona in _DELIBERATIVE_PERSONAS
    ]


def _message_to_turn(message: ChatMessageContent) -> AgentTurn | None:
    if message.role != AuthorRole.ASSISTANT:
        return None
    name = message.name or ""
    if name not in _GODDESS_NAMES:
        return None
    persona = next(p for p in _DELIBERATIVE_PERSONAS if p.name == name)
    content = (message.content or "").strip()
    if not content:
        return None
    return AgentTurn(agent=persona.name, role_label=persona.role_label, content=content)


async def run_deliberation_group_chat(
    *,
    initial_user_prompt: str,
    settings: Settings,
    on_event: EventCallback | None = None,
    prior_turns: list[AgentTurn] | None = None,
) -> list[AgentTurn]:
    """AgentGroupChat で 3 女神合議を実行し、AgentTurn リストを返す（モデレーター除く）。"""

    kernel = build_chat_kernel(settings)
    agents = _build_deliberation_agents(kernel)

    extra_selection_function = KernelFunctionFromPrompt(
        function_name="norn_extra_selection",
        prompt=_EXTRA_SELECTION_PROMPT,
    )
    extra_needed_function = KernelFunctionFromPrompt(
        function_name="norn_extra_needed",
        prompt=_EXTRA_NEEDED_PROMPT,
    )

    selection = NornDeliberationSelectionStrategy(
        kernel=kernel,
        initial_agent=agents[0],
        extra_selection_function=extra_selection_function,
    )
    termination = NornDeliberationTerminationStrategy(
        kernel=kernel,
        extra_needed_function=extra_needed_function,
        maximum_iterations=settings.norn_group_chat_max_iterations,
    )

    chat = AgentGroupChat(
        agents=agents,
        selection_strategy=selection,
        termination_strategy=termination,
    )

    if on_event is not None:
        await on_event(
            {
                "type": "routing_decided",
                "mode": "full_consensus",
                "agents": ["urd", "verdandi", "skuld", "moderator"],
            }
        )

    await chat.add_chat_message(
        ChatMessageContent(role=AuthorRole.USER, content=initial_user_prompt)
    )

    transcript: list[AgentTurn] = list(prior_turns or [])
    seen_turn_keys: set[tuple[str, str]] = {
        (t.agent, t.content[:80]) for t in transcript
    }

    async for message in chat.invoke():
        turn = _message_to_turn(message)
        if turn is None:
            continue
        key = (turn.agent, turn.content[:80])
        if key in seen_turn_keys:
            continue
        seen_turn_keys.add(key)
        transcript.append(turn)
        logger.info(
            "group_chat turn agent=%s chars=%d",
            turn.agent,
            len(turn.content),
        )
        if on_event is not None:
            await on_event({"type": "turn", "turn": turn.model_dump()})

    if prior_turns is None:
        return [t for t in transcript if t.agent in _GODDESS_NAMES]
    return transcript
