"""成長コンテキストの構築と合議後の振り返り（Long-term Memory + Reflection）。"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field

from norn.agents.llm import ChatMessage, LLMClient
from norn.agents.personas import NORN_AGENT_NAMES
from norn.agents.schemas import UserLevel
from norn.db.repositories import (
    append_agent_memory,
    get_or_create_learner_profile,
    list_agent_memories,
    prune_agent_memories,
    update_learner_profile,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from norn.agents.schemas import AgentTurn, ConsensusOutput
    from norn.db.models import AgentMemory, LearnerProfile

logger = logging.getLogger("norn.agents.growth")

_MAX_MEMORY_LINES = 5
_MAX_HISTORY_CHARS = 2000
_MAX_LEARNER_HISTORY_CHARS = 1500

MemoryType = Literal["preference", "pattern", "successful_example"]
MemoryScope = Literal["global", "user"]


class AgentMemoryEntry(BaseModel):
    agent_name: Literal["urd", "verdandi", "skuld"]
    scope: MemoryScope = "user"
    memory_type: MemoryType = "pattern"
    content: str = Field(min_length=1, max_length=500)


class ReflectionOutput(BaseModel):
    growth_summary: str = Field(max_length=600)
    active_goals: list[str] = Field(default_factory=list, max_length=8)
    resolved_topics: list[str] = Field(default_factory=list, max_length=8)
    weak_areas: list[str] = Field(default_factory=list, max_length=8)
    skill_level: UserLevel = "junior"
    agent_memories: list[AgentMemoryEntry] = Field(default_factory=list, max_length=9)
    global_memories: list[AgentMemoryEntry] = Field(default_factory=list, max_length=3)


@dataclass(slots=True)
class GrowthContext:
    """合議前に ReviewContext へ注入する成長コンテキスト。"""

    learner_history: str
    agent_memories: dict[str, str]
    learning_resources: str
    skill_level: UserLevel


async def build_growth_context(
    session: AsyncSession,
    *,
    user_id: int | None,
    user_level: UserLevel,
) -> GrowthContext:
    if user_id is None:
        return GrowthContext(
            learner_history="（成長履歴はまだありません）",
            agent_memories={},
            learning_resources="",
            skill_level=user_level,
        )

    profile = await get_or_create_learner_profile(session, user_id, skill_level=user_level)
    skill_level = _effective_skill_level(profile, user_level)
    learner_history = _render_learner_history(profile)
    agent_memories = await _render_agent_memory_blocks(session, user_id)
    from norn.agents.rag import search_learning_resources

    resources = await search_learning_resources(session, profile.weak_areas)
    return GrowthContext(
        learner_history=learner_history,
        agent_memories=agent_memories,
        learning_resources=resources,
        skill_level=skill_level,
    )


def _effective_skill_level(profile: LearnerProfile, fallback: UserLevel) -> UserLevel:
    if profile.skill_level in {"junior", "mid", "senior"}:
        return profile.skill_level  # type: ignore[return-value]
    return fallback


class PostSessionReflector:
    """合議完了後にプロファイルと女神メモリを更新する。"""

    def __init__(self, llm: LLMClient | None = None) -> None:
        self._llm = llm

    async def reflect_and_persist(
        self,
        session: AsyncSession,
        *,
        user_id: int | None,
        user_level: UserLevel,
        consensus: ConsensusOutput | None,
        transcript: list[AgentTurn],
        user_input: str,
        source_session_id: str | None = None,
    ) -> None:
        if user_id is None or consensus is None:
            return

        profile = await get_or_create_learner_profile(session, user_id, skill_level=user_level)
        reflection = await self._reflect(
            profile=profile,
            consensus=consensus,
            transcript=transcript,
            user_input=user_input,
        )
        await update_learner_profile(
            session,
            user_id,
            skill_level=reflection.skill_level,
            growth_summary=reflection.growth_summary,
            active_goals=reflection.active_goals,
            resolved_topics=reflection.resolved_topics,
            weak_areas=reflection.weak_areas,
            review_count=profile.review_count + 1,
        )

        for entry, scope, uid in (
            *((e, e.scope, user_id) for e in reflection.agent_memories),
            *((e, "global", None) for e in reflection.global_memories),
        ):
            await append_agent_memory(
                session,
                agent_name=entry.agent_name,
                scope=scope,
                user_id=uid,
                memory_type=entry.memory_type,
                content=entry.content,
                source_session_id=source_session_id,
            )
        await prune_agent_memories(session, user_id=user_id)

    async def _reflect(
        self,
        *,
        profile: LearnerProfile,
        consensus: ConsensusOutput,
        transcript: list[AgentTurn],
        user_input: str,
    ) -> ReflectionOutput:
        if self._llm is not None:
            try:
                return await self._reflect_with_llm(
                    profile=profile,
                    consensus=consensus,
                    transcript=transcript,
                    user_input=user_input,
                )
            except Exception:
                logger.exception("LLM reflection failed, falling back to heuristic")
        return _heuristic_reflection(profile, consensus, transcript)

    async def _reflect_with_llm(
        self,
        *,
        profile: LearnerProfile,
        consensus: ConsensusOutput,
        transcript: list[AgentTurn],
        user_input: str,
    ) -> ReflectionOutput:
        assert self._llm is not None
        transcript_text = "\n\n".join(
            f"【{t.role_label}】\n{t.content[:400]}" for t in transcript[-6:]
        )
        prompt = (
            "以下の合議結果を踏まえ、若手エンジニアの成長プロファイルと"
            "各女神が次回活かすべきメモリを JSON で返してください。\n"
            "URL は捏造しない。global_memories は個人名・PR 本文を含めない一般化パターンのみ。\n\n"
            f"# 現在のプロファイル\n"
            f"- skill_level: {profile.skill_level}\n"
            f"- growth_summary: {profile.growth_summary or '（なし）'}\n"
            f"- active_goals: {profile.active_goals}\n"
            f"- weak_areas: {profile.weak_areas}\n\n"
            f"# 若手の入力\n{user_input[:500]}\n\n"
            f"# 合議結果\n"
            f"- summary: {consensus.summary[:400]}\n"
            f"- must_fix: {consensus.must_fix}\n"
            f"- next_pr: {consensus.next_pr}\n"
            f"- growth: {consensus.growth}\n"
            f"- tone: {consensus.tone}\n\n"
            f"# 合議ログ（抜粋）\n{transcript_text}"
        )
        messages = [
            ChatMessage(role="system", content=_REFLECTOR_SYSTEM),
            ChatMessage(role="user", content=prompt),
        ]
        raw = await self._llm.complete(messages, response_format=ReflectionOutput)
        return ReflectionOutput.model_validate_json(raw)


_REFLECTOR_SYSTEM = (
    "あなたは Norns の成長記録モジュールです。"
    "若手の成長と女神の応答改善のため、構造化 JSON のみを返してください。"
)


def _heuristic_reflection(
    profile: LearnerProfile,
    consensus: ConsensusOutput,
    transcript: list[AgentTurn],
) -> ReflectionOutput:
    goals = list(profile.active_goals or [])
    for item in consensus.next_pr[:3]:
        if item and item not in goals:
            goals.append(item)
    if consensus.growth and consensus.growth not in goals:
        goals.insert(0, consensus.growth)
    goals = goals[:8]

    weak = list(profile.weak_areas or [])
    for item in consensus.must_fix[:2]:
        if item and item not in weak:
            weak.append(item)
    weak = weak[:8]

    summary_parts = []
    if profile.growth_summary:
        summary_parts.append(profile.growth_summary[:200])
    if consensus.growth:
        summary_parts.append(consensus.growth[:200])
    growth_summary = " ".join(summary_parts)[:600]

    skill = _estimate_skill_level(profile.review_count + 1, weak)
    agent_memories: list[AgentMemoryEntry] = []
    global_memories: list[AgentMemoryEntry] = []
    for turn in transcript:
        if turn.agent not in NORN_AGENT_NAMES:
            continue
        snippet = turn.content.strip()[:120]
        if snippet:
            agent_memories.append(
                AgentMemoryEntry(
                    agent_name=turn.agent,  # type: ignore[arg-type]
                    scope="user",
                    memory_type="pattern",
                    content=f"効果的だった指摘: {snippet}",
                )
            )
        if len(agent_memories) >= 3:
            break

    if consensus.tone == "encouraging" and consensus.growth:
        global_memories.append(
            AgentMemoryEntry(
                agent_name="skuld",
                scope="global",
                memory_type="successful_example",
                content=f"成長提案が好評: {consensus.growth[:100]}",
            )
        )

    return ReflectionOutput(
        growth_summary=growth_summary,
        active_goals=goals,
        resolved_topics=list(profile.resolved_topics or [])[:8],
        weak_areas=weak,
        skill_level=skill,
        agent_memories=agent_memories,
        global_memories=global_memories,
    )


def _estimate_skill_level(review_count: int, weak_areas: list[str]) -> UserLevel:
    if review_count >= 15 and len(weak_areas) <= 2:
        return "senior"
    if review_count >= 5 or len(weak_areas) <= 4:
        return "mid"
    return "junior"


def _render_learner_history(profile: LearnerProfile) -> str:
    lines = [
        f"- レビュー回数: {profile.review_count}",
        f"- 推定スキルレベル: {profile.skill_level}",
    ]
    if profile.growth_summary:
        lines.append(f"- 成長サマリー: {profile.growth_summary[:400]}")
    if profile.active_goals:
        lines.append("- 学習目標:")
        lines.extend(f"  - {g}" for g in profile.active_goals[:5])
    if profile.weak_areas:
        lines.append("- 繰り返しの弱点:")
        lines.extend(f"  - {w}" for w in profile.weak_areas[:5])
    if profile.resolved_topics:
        lines.append("- 解決済みトピック:")
        lines.extend(f"  - {r}" for r in profile.resolved_topics[:5])
    text = "\n".join(lines)
    if len(text) > _MAX_LEARNER_HISTORY_CHARS:
        return text[:_MAX_LEARNER_HISTORY_CHARS] + "…"
    return text or "（成長履歴はまだありません）"


async def _fetch_memories_for_agent(
    session: AsyncSession,
    *,
    agent: str,
    user_id: int,
) -> tuple[list[AgentMemory], list[AgentMemory]]:
    user_memories = await list_agent_memories(
        session, agent_name=agent, user_id=user_id, scope="user", limit=_MAX_MEMORY_LINES
    )
    global_memories = await list_agent_memories(
        session, agent_name=agent, scope="global", user_id=None, limit=3
    )
    return user_memories, global_memories


async def _render_agent_memory_blocks(session: AsyncSession, user_id: int) -> dict[str, str]:
    blocks: dict[str, str] = {}
    for agent in NORN_AGENT_NAMES:
        user_memories, global_memories = await _fetch_memories_for_agent(
            session, agent=agent, user_id=user_id
        )
        lines: list[str] = []
        for mem in user_memories:
            lines.append(f"- {mem.content}")
        for mem in global_memories:
            lines.append(f"- [チーム共通] {mem.content}")
        if lines:
            blocks[agent] = "\n".join(lines[: _MAX_MEMORY_LINES + 3])
    return blocks


def render_chat_history(messages: list[tuple[str, str]], *, exclude_last: bool = True) -> str:
    """(role, content) のリストからチャット履歴テキストを生成。"""
    rows = messages[:-1] if exclude_last and messages else messages
    if not rows:
        return ""
    lines: list[str] = []
    for role, content in rows[-10:]:
        label = "若手" if role == "user" else "Norns"
        snippet = content.strip()[:300]
        if snippet:
            lines.append(f"【{label}】\n{snippet}")
    text = "\n\n".join(lines)
    if len(text) > _MAX_HISTORY_CHARS:
        return text[-_MAX_HISTORY_CHARS:]
    return text
