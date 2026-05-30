"""PR コメント用 Markdown レンダラ。

セルフループ防止のため、本文先頭に `<!-- norn:session=<uuid> -->` マーカーを必ず置く。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from norn.agents.schemas import ConsensusOutput


def render_pr_comment(
    output: ConsensusOutput,
    *,
    session_id: str,
    thread_link: str | None = None,
) -> str:
    parts: list[str] = []
    parts.append(f"<!-- norn:session={session_id} -->")
    parts.append("## 🌿 Norn からの伴走レビュー")
    parts.append(output.summary.strip())

    if output.must_fix:
        parts.append("\n### いま直したいこと")
        parts.extend(f"- {item}" for item in output.must_fix)

    if output.next_pr:
        parts.append("\n### 次の PR で")
        parts.extend(f"- {item}" for item in output.next_pr)

    if output.growth:
        parts.append("\n### 成長機会")
        parts.append(output.growth.strip())

    if thread_link:
        parts.append("\n---")
        parts.append(f"Norn と続きを話す: {thread_link}")

    return "\n".join(parts)


def render_failure_comment(*, session_id: str) -> str:
    return (
        f"<!-- norn:session={session_id} -->\n"
        "Norn は今回コメントを差し控えました。少し時間をおいて再度トリガーしてください。"
    )
