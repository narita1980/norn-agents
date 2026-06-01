"""3 女神 + Consensus Moderator の合議オーケストレータ。

ウルド（メンター）とスクルド（キャリア）を並行実行し、両方の回答が揃ってから
ヴェルダンディ（伴走）→ モデレーターの順で進める。
`NORN_ORCHESTRATION_MODE=group_chat` は従来名の互換用（中身は同一フロー）。

チャット経路（PR コンテキストなし）では Routing Moderator が
フル合議か単一女神応答かを先に決める。
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Annotated, Any, Literal, Protocol

from fastapi import Depends, HTTPException, status
from pydantic import ValidationError
from semantic_kernel.exceptions.service_exceptions import ServiceInitializationError

from norn.agents.llm import AzureLLMClient, ChatMessage, LLMClient
from norn.agents.personas import (
    COMPANION_VERDANDI,
    MODERATOR,
    ROUTING_MODERATOR,
    SKULD,
    URD,
    VERDANDI,
    Persona,
)
from norn.agents.schemas import (
    AgentTurn,
    ConsensusOutput,
    ConsensusResult,
    ReviewContext,
    RoutingDecision,
)
from norn.agents.user_levels import render_user_level_block
from norn.config import Settings, get_settings

EventCallback = Callable[[dict[str, Any]], Awaitable[None]]

logger = logging.getLogger("norn.agents.orchestrator")

_DELIBERATIVE_PERSONAS: tuple[Persona, ...] = (URD, SKULD, VERDANDI)
_PARALLEL_PERSONAS: tuple[Persona, ...] = (URD, SKULD)
_PERSONA_BY_NAME: dict[str, Persona] = {
    URD.name: URD,
    VERDANDI.name: VERDANDI,
    SKULD.name: SKULD,
}
_FULL_PIPELINE: tuple[str, ...] = ("urd", "skuld", "verdandi", "moderator")
SingleAgentName = Literal["urd", "verdandi", "skuld"]

# patch を全部送ると context が爆発するので 1 ファイル当たり先頭 200 行で抜粋する。
_PATCH_HEAD_LINES = 200

# ルーティング LLM の取りこぼし防止（開発無関係の典型パターン）。
_OUT_OF_SCOPE_HINTS: tuple[str, ...] = (
    "天気",
    "気温",
    "降水",
    "weather",
    "forecast",
    "ニュース",
    "株価",
    "レシピ",
    "占い",
    "映画",
    "ドラマ",
)

# コード差分なしの一般相談 → 伴走（out_of_scope）へ寄せるヒント。
_COMPANION_CHAT_HINTS: tuple[str, ...] = (
    "うまくな",
    "上手くな",
    "モチベ",
    "成長",
    "勉強",
    "学び方",
    "初心者",
    "つらい",
    "苦しい",
    "諦め",
    "アドバイス",
    "どうすれば",
    "どうやって覚",
    "キャリア",
    "雑談",
    "おすすめ",
)

_CODE_REVIEW_HINTS: tuple[str, ...] = (
    "```",
    "def ",
    "class ",
    "function ",
    "import ",
    "pr #",
    "pull request",
    "diff",
    "リファクタ",
    "設計",
    "アーキテク",
    "バグ",
    "レビュー",
)


class OrchestratorProtocol(Protocol):
    async def run(
        self,
        context: ReviewContext,
        *,
        on_event: EventCallback | None = None,
    ) -> ConsensusResult: ...


class NornOrchestrator:
    """合議の本体。LLMClient を差し替えればテスト可能。

    `on_event` を渡すと、各ターン完了時 / 最終合議完了時に dict 形式の
    イベントを発火する。配信用途（SSE 等）は呼び出し側で組み立てる。
    """

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    async def run(
        self,
        context: ReviewContext,
        *,
        on_event: EventCallback | None = None,
    ) -> ConsensusResult:
        if context.is_pr_context:
            if on_event is not None:
                await on_event(
                    {
                        "type": "routing_decided",
                        "mode": "full_consensus",
                        "agents": list(_FULL_PIPELINE),
                    }
                )
            return await self._run_full(context, on_event=on_event)

        decision = (
            RoutingDecision(mode="out_of_scope", agent=None)
            if _should_use_companion(context.user_input)
            else await self._route(context)
        )
        if on_event is not None:
            await on_event(
                {
                    "type": "routing_decided",
                    "mode": decision.mode,
                    "agents": pipeline_agents(decision),
                }
            )

        if decision.mode == "out_of_scope":
            return await self._run_out_of_scope(context, on_event=on_event)
        if decision.mode == "single_agent" and decision.agent is not None:
            return await self._run_single(context, decision.agent, on_event=on_event)
        return await self._run_full(context, on_event=on_event)

    async def _route(self, context: ReviewContext) -> RoutingDecision:
        messages = [
            ChatMessage(role="system", content=ROUTING_MODERATOR.system_prompt),
            ChatMessage(
                role="user",
                content=(
                    f"{render_user_level_block(context.user_level)}\n\n"
                    "# 若手エンジニアからの入力\n"
                    f"{_render_user_input(context)}\n\n"
                    "上記に対する routing JSON を返してください。"
                ),
            ),
        ]
        try:
            raw = await self._llm.complete(messages, response_format=RoutingDecision)
            decision = RoutingDecision.model_validate_json(raw)
            if decision.mode == "full_consensus" and not _looks_like_code_review(context.user_input):
                logger.info(
                    "routing downgraded full_consensus -> out_of_scope (no code signals)"
                )
                return RoutingDecision(mode="out_of_scope", agent=None)
            return decision
        except (ValidationError, json.JSONDecodeError) as exc:
            logger.warning("routing decision invalid, fallback: %s", exc)
            return _routing_fallback(context.user_input)

    async def _run_full(
        self,
        context: ReviewContext,
        *,
        on_event: EventCallback | None = None,
    ) -> ConsensusResult:
        transcript = await self._run_deliberative_parallel(context, on_event=on_event)
        return await self._finalize_with_moderator(context, transcript, on_event=on_event)

    async def _run_full_group_chat(
        self,
        context: ReviewContext,
        *,
        on_event: EventCallback | None = None,
    ) -> ConsensusResult:
        # 互換名。AgentGroupChat 逐次合議から並行合議へ移行済み。
        transcript = await self._run_deliberative_parallel(context, on_event=on_event)
        return await self._finalize_with_moderator(context, transcript, on_event=on_event)

    async def _complete_persona_turn(
        self,
        context: ReviewContext,
        persona: Persona,
        prior: str,
    ) -> AgentTurn:
        user_content = _build_user_prompt(context, prior, persona_name=persona.name)
        messages = [
            ChatMessage(role="system", content=persona.system_prompt),
            ChatMessage(role="user", content=user_content),
        ]
        content = await self._llm.complete(messages)
        return AgentTurn(
            agent=persona.name, role_label=persona.role_label, content=content
        )

    async def _run_deliberative_parallel(
        self,
        context: ReviewContext,
        *,
        on_event: EventCallback | None = None,
    ) -> list[AgentTurn]:
        """ウルド・スクルドを並行 → ヴェルダンディの 3 段合議（モデレーター除く）。"""

        transcript: list[AgentTurn] = list(context.prior_turns)
        base_prior = _format_prior_turns(transcript)

        tasks = [
            asyncio.create_task(
                self._complete_persona_turn(context, persona, base_prior),
                name=persona.name,
            )
            for persona in _PARALLEL_PERSONAS
        ]
        parallel_turns: list[AgentTurn] = []
        for coro in asyncio.as_completed(tasks):
            turn = await coro
            parallel_turns.append(turn)
            logger.info(
                "agent turn complete agent=%s chars=%d", turn.agent, len(turn.content)
            )
            if on_event is not None:
                await on_event({"type": "turn", "turn": turn.model_dump()})

        parallel_turns.sort(key=lambda t: 0 if t.agent == URD.name else 1)
        transcript.extend(parallel_turns)

        prior = _format_prior_turns(transcript)
        verdandi_turn = await self._complete_persona_turn(context, VERDANDI, prior)
        transcript.append(verdandi_turn)
        logger.info(
            "agent turn complete agent=%s chars=%d",
            verdandi_turn.agent,
            len(verdandi_turn.content),
        )
        if on_event is not None:
            await on_event({"type": "turn", "turn": verdandi_turn.model_dump()})

        return transcript

    async def _run_single(
        self,
        context: ReviewContext,
        agent: SingleAgentName,
        *,
        on_event: EventCallback | None = None,
    ) -> ConsensusResult:
        persona = _PERSONA_BY_NAME[agent]
        transcript: list[AgentTurn] = list(context.prior_turns)
        prior = _format_prior_turns(transcript)
        messages = [
            ChatMessage(role="system", content=persona.system_prompt),
            ChatMessage(role="user", content=_build_user_prompt(context, prior, persona_name=persona.name)),
        ]
        content = await self._llm.complete(messages)
        turn = AgentTurn(agent=persona.name, role_label=persona.role_label, content=content)
        transcript.append(turn)
        logger.info("single-agent turn complete agent=%s chars=%d", persona.name, len(content))
        if on_event is not None:
            await on_event({"type": "turn", "turn": turn.model_dump()})

        return await self._finalize_with_moderator(context, transcript, on_event=on_event)

    async def _run_out_of_scope(
        self,
        context: ReviewContext,
        *,
        on_event: EventCallback | None = None,
    ) -> ConsensusResult:
        messages = [
            ChatMessage(role="system", content=COMPANION_VERDANDI.system_prompt),
            ChatMessage(
                role="user",
                content=(
                    f"{render_user_level_block(context.user_level)}\n\n"
                    "# 若手エンジニアからの入力\n"
                    f"{_render_user_input(context)}\n\n"
                    "上記に対して、伴走メンターとして返信してください。"
                ),
            ),
        ]
        content = (await self._llm.complete(messages)).strip()
        output = ConsensusOutput(
            summary=content,
            must_fix=[],
            next_pr=[],
            growth="",
            tone="neutral",
        )
        turn = AgentTurn(
            agent=COMPANION_VERDANDI.name,
            role_label=COMPANION_VERDANDI.role_label,
            content=content,
        )
        logger.info("out-of-scope reply chars=%d", len(content))
        if on_event is not None:
            await on_event({"type": "turn", "turn": turn.model_dump()})
            await on_event(
                {"type": "consensus_ready", "consensus": output.model_dump()}
            )
        return ConsensusResult(output=output, transcript=[turn])

    async def _finalize_with_moderator(
        self,
        context: ReviewContext,
        transcript: list[AgentTurn],
        *,
        on_event: EventCallback | None = None,
    ) -> ConsensusResult:
        prior = _format_prior_turns(transcript)
        moderator_messages = [
            ChatMessage(role="system", content=MODERATOR.system_prompt),
            ChatMessage(role="user", content=_build_moderator_prompt(context, prior)),
        ]
        raw = await self._llm.complete(moderator_messages, response_format=ConsensusOutput)
        output = _parse_consensus(raw)
        moderator_turn = AgentTurn(
            agent=MODERATOR.name,
            role_label=MODERATOR.role_label,
            content=(
                f"3 女神の合議を踏まえ、最終レビューにまとめました。\n\n{output.summary}"
            ),
        )
        transcript.append(moderator_turn)
        if on_event is not None:
            await on_event({"type": "turn", "turn": moderator_turn.model_dump()})
            await on_event(
                {"type": "consensus_ready", "consensus": output.model_dump()}
            )
        return ConsensusResult(output=output, transcript=transcript)


def _should_use_companion(user_input: str) -> bool:
    text = user_input.strip().lower()
    if not text:
        return False
    if _looks_like_code_review(text):
        return False
    return _is_likely_out_of_scope(text) or _is_likely_companion_chat(text)


def _is_likely_out_of_scope(user_input: str) -> bool:
    text = user_input.strip().lower()
    if not text:
        return False
    return any(hint in text for hint in _OUT_OF_SCOPE_HINTS)


def _is_likely_companion_chat(user_input: str) -> bool:
    text = user_input.strip().lower()
    if not text:
        return False
    return any(hint in text for hint in _COMPANION_CHAT_HINTS)


def _looks_like_code_review(user_input: str) -> bool:
    text = user_input.strip().lower()
    if not text:
        return False
    return any(hint in text for hint in _CODE_REVIEW_HINTS)


def _routing_fallback(user_input: str) -> RoutingDecision:
    if _looks_like_code_review(user_input):
        return RoutingDecision(mode="full_consensus", agent=None)
    return RoutingDecision(mode="out_of_scope", agent=None)


def pipeline_agents(decision: RoutingDecision) -> list[str]:
    if decision.mode == "out_of_scope":
        return [COMPANION_VERDANDI.name]
    if decision.mode == "single_agent" and decision.agent is not None:
        return [decision.agent, MODERATOR.name]
    return list(_FULL_PIPELINE)


def _format_prior_turns(transcript: list[AgentTurn]) -> str:
    if not transcript:
        return "（前段の発言はありません。あなたが最初の話者です。）"
    lines = []
    for turn in transcript:
        lines.append(f"【{turn.role_label}】\n{turn.content}")
    return "\n\n".join(lines)


def _build_user_prompt(
    context: ReviewContext, prior: str, *, persona_name: str | None = None
) -> str:
    sections: list[str] = []
    sections.append(render_user_level_block(context.user_level))

    if context.learner_history:
        sections.append("# この若手の成長履歴")
        sections.append(context.learner_history)

    if persona_name and context.agent_memories.get(persona_name):
        sections.append(f"# あなた（{persona_name}）のこれまでの学び")
        sections.append(context.agent_memories[persona_name])

    if persona_name == SKULD.name and context.learning_resources:
        sections.append(context.learning_resources)

    if context.chat_history and not context.is_pr_context:
        sections.append("# このスレッドの過去のやり取り")
        sections.append(context.chat_history)

    sections.append("# 若手エンジニアからの入力")
    sections.append(_render_user_input(context))

    if context.is_pr_context:
        sections.append("# PR メタ情報")
        sections.append(_render_pr_meta(context))

        sections.append(f"# 変更ファイル一覧 (n={len(context.files)})")
        sections.append(_render_files(context))

        sections.append("# Diff（各ファイル先頭 200 行抜粋）")
        sections.append(_render_diffs(context))

        sections.append("# 静的解析 (Ruff)")
        sections.append(_render_ruff(context))

        sections.append(f"# コミット履歴 (n={len(context.commits)})")
        sections.append(_render_commits(context))

    if not context.is_pr_context:
        sections.append("# 注意")
        sections.append(
            "この入力は PR やコード差分を伴いません。"
            "ソフトウェア開発・学習と無関係な内容なら、"
            "あなたの担当外である旨だけを短く書き、PR レビューの定型句は使わないでください。"
        )

    sections.append("# これまでの合議ログ")
    sections.append(prior)

    sections.append("# 応答形式")
    sections.append(
        "上記ログを読んだうえで、**合議の続き**として自然な会話口調で書いてください。\n"
        "ウルドとスクルドは並行で初回分析するため、互いの発言はまだありません。"
        "ヴェルダンディ向けに、あなたの担当視点だけを渡してください。\n"
        "ヴェルダンディはウルド・スクルド両方の発言を受けて締めます。"
        "その場合は二人の名前を出して受け答えする体裁にします。\n"
        "冒頭 1〜2 文は必ず発言口調とし、必要ならその後に箇条書きを続けてください。"
    )

    sections.append("# あなたの役割に従って応答してください。")

    return "\n\n".join(sections)


def _build_moderator_prompt(context: ReviewContext, prior: str) -> str:
    intro_sections: list[str] = []
    intro_sections.append(render_user_level_block(context.user_level))

    if context.learner_history:
        intro_sections.append("# この若手の成長履歴")
        intro_sections.append(context.learner_history)

    intro_sections.append("# 若手エンジニアからの入力")
    intro_sections.append(_render_user_input(context))

    if context.is_pr_context:
        intro_sections.append("# PR メタ情報")
        intro_sections.append(_render_pr_meta(context))

    intro_sections.append("# 三女神の発言ログ")
    intro_sections.append(prior)
    if context.is_pr_context:
        intro_sections.append(
            "上記を踏まえ、定められた JSON スキーマで**最終レビュー**を 1 つだけ返してください。"
        )
    else:
        intro_sections.append(
            "上記を踏まえ、定められた JSON スキーマで返してください。\n"
            "入力がコードや PR と無関係な場合: summary に女神の案内を要約し、"
            "must_fix / next_pr / growth は空（growth は \"\"、配列は []）。"
            "存在しない PR への言及や『技術的懸念はありません』などのレビュー定型句は禁止。"
        )

    return "\n\n".join(intro_sections)


def _render_user_input(context: ReviewContext) -> str:
    if context.user_reply:
        return f"（PR コメントで届いた返信）\n{context.user_reply}"
    return context.user_input or "（特に入力はありません。PR の内容から判断してください。）"


def _render_pr_meta(context: ReviewContext) -> str:
    head = (context.head_sha or "")[:7] or "?"
    base = (context.base_sha or "")[:7] or "?"
    return (
        f"リポジトリ: {context.repository}\n"
        f"PR #{context.pr_number}: {context.pr_title or ''}\n"
        f"HEAD: {head} ({context.head_ref or '?'}) → BASE: {base} ({context.base_ref or '?'})"
    )


def _render_files(context: ReviewContext) -> str:
    if not context.files:
        return "（変更ファイルは見つかりませんでした）"
    return "\n".join(
        f"- {f.path} ({f.status}, +{f.additions} -{f.deletions})" for f in context.files
    )


def _render_diffs(context: ReviewContext) -> str:
    if not context.files:
        return "（差分はありません）"
    chunks: list[str] = []
    for f in context.files:
        if not f.patch:
            chunks.append(f"## {f.path}\n（patch は省略されました）")
            continue
        lines = f.patch.splitlines()
        truncated = ""
        if len(lines) > _PATCH_HEAD_LINES:
            lines = lines[:_PATCH_HEAD_LINES]
            truncated = f"\n... (先頭 {_PATCH_HEAD_LINES} 行のみ抜粋)"
        chunks.append(f"## {f.path}\n```diff\n" + "\n".join(lines) + "\n```" + truncated)
    return "\n\n".join(chunks)


def _render_ruff(context: ReviewContext) -> str:
    if not context.ruff_findings:
        return "（Ruff の指摘はありません）"
    lines = [f"- {f.file}:{f.line} {f.code} {f.message}" for f in context.ruff_findings]
    if context.ruff_truncated:
        lines.append("※ 大規模 PR のため先頭 50 ファイルで打ち切り。")
    return "\n".join(lines)


def _render_commits(context: ReviewContext) -> str:
    if not context.commits:
        return "（コミット情報はありません）"
    lines = []
    for c in context.commits:
        subject = c.message.splitlines()[0] if c.message else ""
        lines.append(f"- {c.sha[:7]} {subject}")
    return "\n".join(lines)


def _parse_consensus(raw: str) -> ConsensusOutput:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("moderator output is not valid JSON: %s", exc)
        raise
    try:
        return ConsensusOutput.model_validate(payload)
    except ValidationError as exc:
        logger.warning("moderator output failed schema validation: %s", exc)
        raise


def get_orchestrator(
    settings: Annotated[Settings, Depends(get_settings)],
) -> NornOrchestrator:
    """FastAPI Depends 用ファクトリ。テストでは override する。"""
    if not settings.llm_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Azure OpenAI is not configured",
        )
    try:
        return NornOrchestrator(AzureLLMClient(settings))
    except ServiceInitializationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Azure OpenAI initialization failed: {exc}",
        ) from exc
