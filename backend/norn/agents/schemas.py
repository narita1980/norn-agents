"""エージェント合議の入出力スキーマ。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AgentTurn(BaseModel):
    """合議中の 1 ターン分の発話。"""

    agent: str = Field(description="urd / verdandi / skuld / moderator")
    role_label: str
    content: str


class ConsensusOutput(BaseModel):
    """Consensus Moderator が出力する最終レビュー。"""

    summary: str
    must_fix: list[str] = Field(default_factory=list, max_length=5)
    next_pr: list[str] = Field(default_factory=list, max_length=5)
    growth: str
    tone: Literal["encouraging", "neutral", "cautious"] = "encouraging"


class ConsensusResult(BaseModel):
    """オーケストレータの戻り値。最終出力 + 合議トレース。"""

    output: ConsensusOutput
    transcript: list[AgentTurn] = Field(default_factory=list)


class ChangedFile(BaseModel):
    """PR の変更ファイル 1 件分。"""

    path: str
    status: str = "modified"
    additions: int = 0
    deletions: int = 0
    patch: str | None = None


class CommitInfo(BaseModel):
    """PR に含まれるコミット 1 件分。"""

    sha: str
    message: str
    author: str = ""


class RuffFinding(BaseModel):
    """Ruff 静的解析の結果 1 件。"""

    file: str
    line: int
    code: str
    message: str


class ReviewContext(BaseModel):
    """オーケストレータへの入力。PR レビュー経路とチャット経路の両方を表す。

    - PR 経路: repository / pr_number / files / commits などを設定。
    - チャット経路: from_user_input() を使うと PR フィールドを空にした最小コンテキストを作れる。
    - 再合議（PR コメント返信）: prior_turns に過去ターン、user_reply に若手の返信を載せる。
    """

    user_input: str = ""
    repository: str | None = None
    pr_number: int | None = None
    pr_title: str | None = None
    pr_body: str | None = None
    pr_url: str | None = None
    head_sha: str | None = None
    base_sha: str | None = None
    head_ref: str | None = None
    base_ref: str | None = None
    files: list[ChangedFile] = Field(default_factory=list)
    commits: list[CommitInfo] = Field(default_factory=list)
    ruff_findings: list[RuffFinding] = Field(default_factory=list)
    ruff_truncated: bool = False
    prior_turns: list[AgentTurn] = Field(default_factory=list)
    user_reply: str | None = None

    @classmethod
    def from_user_input(cls, text: str) -> ReviewContext:
        return cls(user_input=text)

    @property
    def is_pr_context(self) -> bool:
        return self.repository is not None and self.pr_number is not None
