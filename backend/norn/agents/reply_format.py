"""合議結果を assistant メッセージ用テキストに整形する。"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from norn.agents.schemas import ConsensusOutput


def render_consensus_reply(output: ConsensusOutput) -> str:
    lines = [output.summary.strip()]
    if output.must_fix:
        lines.append("\n**いま直したいこと**")
        lines.extend(f"- {item}" for item in output.must_fix)
    if output.next_pr:
        lines.append("\n**次の PR で**")
        lines.extend(f"- {item}" for item in output.next_pr)
    if output.growth:
        lines.append("\n**成長機会**")
        lines.append(output.growth.strip())
    return "\n".join(lines)
