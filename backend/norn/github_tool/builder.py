"""ReviewContext を組み立てる convenience。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from norn.agents.schemas import ReviewContext
from norn.github_tool.ruff_runner import run_ruff_on_snapshot

if TYPE_CHECKING:
    from norn.agents.schemas import AgentTurn
    from norn.github_tool.client import GitHubClientProtocol

NORN_COMMENT_MARKER = "<!-- norn:session="


async def build_review_context(
    client: GitHubClientProtocol,
    payload: dict[str, Any],
    *,
    prior_turns: list[AgentTurn] | None = None,
    user_reply: str | None = None,
) -> ReviewContext:
    """Webhook payload から ReviewContext を構築する。

    `payload` は GitHub の pull_request / issue_comment いずれの形でも OK。
    """

    repository = _extract_repository(payload)
    pr_number = _extract_pr_number(payload)
    if repository is None or pr_number is None:
        raise ValueError("payload does not contain repository / pr_number")

    snap = await client.fetch_pull_request(repository, pr_number)
    ruff_findings, truncated = await run_ruff_on_snapshot(client, snap)

    return ReviewContext(
        user_input="",
        repository=snap.repository,
        pr_number=snap.pr_number,
        pr_title=snap.title,
        pr_body=snap.body,
        pr_url=snap.html_url,
        head_sha=snap.head_sha,
        base_sha=snap.base_sha,
        head_ref=snap.head_ref,
        base_ref=snap.base_ref,
        files=list(snap.files),
        commits=list(snap.commits),
        ruff_findings=ruff_findings,
        ruff_truncated=truncated,
        prior_turns=list(prior_turns or []),
        user_reply=user_reply,
    )


def _extract_repository(payload: dict[str, Any]) -> str | None:
    repo = payload.get("repository") or {}
    return repo.get("full_name")


def _extract_pr_number(payload: dict[str, Any]) -> int | None:
    pr = payload.get("pull_request") or {}
    if "number" in pr:
        return pr["number"]
    issue = payload.get("issue") or {}
    if "number" in issue:
        return issue["number"]
    if "number" in payload:
        return payload["number"]
    return None
