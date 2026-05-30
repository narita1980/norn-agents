"""PR コメント経由の再合議フロー（issue_comment.created）の統合テスト。"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest
    from fastapi.testclient import TestClient


def _dispatch_initial_pr(
    client: TestClient,
    github_pull_request_payload: bytes,
    github_signature,
) -> None:
    response = client.post(
        "/webhook/github",
        content=github_pull_request_payload,
        headers={
            "X-Hub-Signature-256": github_signature(github_pull_request_payload),
            "X-GitHub-Event": "pull_request",
            "X-GitHub-Delivery": "aaaa",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 202


def test_issue_comment_triggers_reply_consensus(
    client: TestClient,
    github_pull_request_payload: bytes,
    github_issue_comment_payload: bytes,
    github_signature,
    fake_orchestrator,
    fake_github_client,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="norn.api.routes.github")

    _dispatch_initial_pr(client, github_pull_request_payload, github_signature)
    assert len(fake_orchestrator.calls) == 1
    assert len(fake_github_client.posted_comments) == 1

    response = client.post(
        "/webhook/github",
        content=github_issue_comment_payload,
        headers={
            "X-Hub-Signature-256": github_signature(github_issue_comment_payload),
            "X-GitHub-Event": "issue_comment",
            "X-GitHub-Delivery": "bbbb",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 202

    assert len(fake_orchestrator.calls) == 2
    reply_ctx = fake_orchestrator.calls[1]
    assert reply_ctx.user_reply is not None
    assert "もう少し例を教えてください" in reply_ctx.user_reply
    assert reply_ctx.prior_turns  # 前回の合議ターンが載っている
    assert any(t.agent == "urd" for t in reply_ctx.prior_turns)

    assert len(fake_github_client.posted_comments) == 2
    _, _, second_body = fake_github_client.posted_comments[1]
    assert second_body.startswith("<!-- norn:session=")


def test_issue_comment_with_norn_marker_is_ignored(
    client: TestClient,
    github_issue_comment_norn_payload: bytes,
    github_signature,
    fake_orchestrator,
    fake_github_client,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="norn.api.routes.github")

    response = client.post(
        "/webhook/github",
        content=github_issue_comment_norn_payload,
        headers={
            "X-Hub-Signature-256": github_signature(github_issue_comment_norn_payload),
            "X-GitHub-Event": "issue_comment",
            "X-GitHub-Delivery": "cccc",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 202
    assert len(fake_orchestrator.calls) == 0
    assert len(fake_github_client.posted_comments) == 0
    assert any("norn marker present" in r.message for r in caplog.records)


def test_issue_comment_on_unknown_pr_is_warned(
    client: TestClient,
    github_issue_comment_payload: bytes,
    github_signature,
    fake_orchestrator,
    fake_github_client,
    caplog: pytest.LogCaptureFixture,
) -> None:
    # review_session を一切作らずに issue_comment を送る
    caplog.set_level(logging.WARNING, logger="norn.api.routes.github")

    response = client.post(
        "/webhook/github",
        content=github_issue_comment_payload,
        headers={
            "X-Hub-Signature-256": github_signature(github_issue_comment_payload),
            "X-GitHub-Event": "issue_comment",
            "X-GitHub-Delivery": "dddd",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 202
    assert len(fake_orchestrator.calls) == 0
    assert len(fake_github_client.posted_comments) == 0
    assert any("unknown PR" in r.message for r in caplog.records)
