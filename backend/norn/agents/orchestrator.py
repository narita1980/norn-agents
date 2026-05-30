"""3 女神 + Consensus Moderator の合議オーケストレータ。

ラウンドロビンではなく、固定順序（Urd → Verdandi → Skuld → Moderator）の
逐次合議。max_round は『persona 数 × 1 ラウンド』に固定し、無限ループを防ぐ。
"""

from __future__ import annotations

import json
import logging
from typing import Protocol

from pydantic import ValidationError

from norn.agents.llm import AzureLLMClient, ChatMessage, LLMClient
from norn.agents.personas import MODERATOR, SKULD, URD, VERDANDI, Persona
from norn.agents.schemas import (
    AgentTurn,
    ConsensusOutput,
    ConsensusResult,
    ReviewContext,
)
from norn.config import get_settings

logger = logging.getLogger("norn.agents.orchestrator")

_DELIBERATIVE_PERSONAS: tuple[Persona, ...] = (URD, VERDANDI, SKULD)

# patch を全部送ると context が爆発するので 1 ファイル当たり先頭 200 行で抜粋する。
_PATCH_HEAD_LINES = 200


class OrchestratorProtocol(Protocol):
    async def run(self, context: ReviewContext) -> ConsensusResult: ...


class NornOrchestrator:
    """合議の本体。LLMClient を差し替えればテスト可能。"""

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    async def run(self, context: ReviewContext) -> ConsensusResult:
        transcript: list[AgentTurn] = list(context.prior_turns)

        for persona in _DELIBERATIVE_PERSONAS:
            prior = _format_prior_turns(transcript)
            messages = [
                ChatMessage(role="system", content=persona.system_prompt),
                ChatMessage(role="user", content=_build_user_prompt(context, prior)),
            ]
            content = await self._llm.complete(messages)
            transcript.append(
                AgentTurn(agent=persona.name, role_label=persona.role_label, content=content)
            )
            logger.info("agent turn complete agent=%s chars=%d", persona.name, len(content))

        prior = _format_prior_turns(transcript)
        moderator_messages = [
            ChatMessage(role="system", content=MODERATOR.system_prompt),
            ChatMessage(role="user", content=_build_moderator_prompt(context, prior)),
        ]
        raw = await self._llm.complete(moderator_messages, response_format=ConsensusOutput)
        output = _parse_consensus(raw)
        transcript.append(
            AgentTurn(
                agent=MODERATOR.name,
                role_label=MODERATOR.role_label,
                content=output.model_dump_json(),
            )
        )
        return ConsensusResult(output=output, transcript=transcript)


def _format_prior_turns(transcript: list[AgentTurn]) -> str:
    if not transcript:
        return "（前段の発言はありません。あなたが最初の話者です。）"
    lines = []
    for turn in transcript:
        lines.append(f"### {turn.role_label}\n{turn.content}")
    return "\n\n".join(lines)


def _build_user_prompt(context: ReviewContext, prior: str) -> str:
    sections: list[str] = []
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

    sections.append("# これまでの合議ログ")
    sections.append(prior)

    sections.append("# あなたの役割に従って応答してください。")

    return "\n\n".join(sections)


def _build_moderator_prompt(context: ReviewContext, prior: str) -> str:
    intro_sections: list[str] = []
    intro_sections.append("# 若手エンジニアからの入力")
    intro_sections.append(_render_user_input(context))

    if context.is_pr_context:
        intro_sections.append("# PR メタ情報")
        intro_sections.append(_render_pr_meta(context))

    intro_sections.append("# 三女神の発言ログ")
    intro_sections.append(prior)
    intro_sections.append(
        "上記を踏まえ、定められた JSON スキーマで**最終レビュー**を 1 つだけ返してください。"
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


def get_orchestrator() -> NornOrchestrator:
    """FastAPI Depends 用ファクトリ。テストでは override する。"""
    return NornOrchestrator(AzureLLMClient(get_settings()))
