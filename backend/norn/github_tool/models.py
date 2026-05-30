"""GitHub PR Snapshot を表すデータクラス。

`ReviewContext` は `norn.agents.schemas` 側で定義し、ここでは PyGithub から取り出した
中間表現を持つ。1 レイヤ挟むことで PyGithub に依存しないテストが書ける。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from norn.agents.schemas import ChangedFile, CommitInfo


@dataclass(frozen=True, slots=True)
class PullRequestSnapshot:
    """PR の状態 1 点のスナップショット。"""

    repository: str
    pr_number: int
    title: str
    body: str
    author: str
    html_url: str
    head_sha: str
    base_sha: str
    head_ref: str
    base_ref: str
    files: list[ChangedFile] = field(default_factory=list)
    commits: list[CommitInfo] = field(default_factory=list)
