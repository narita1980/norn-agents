"""github_tool パッケージのテスト。

- builder.build_review_context: payload → ReviewContext の組み立て
- ruff_runner.run_ruff_on_snapshot: 実 Ruff を tempdir で走らせて parse する
"""

from __future__ import annotations

import pytest

from norn.agents.schemas import AgentTurn, ChangedFile, CommitInfo, ConsensusOutput
from norn.github_tool.builder import build_review_context
from norn.github_tool.markdown import render_pr_comment
from norn.github_tool.models import PullRequestSnapshot
from norn.github_tool.ruff_runner import run_ruff_on_snapshot


@pytest.fixture
def snap_with_py_file() -> PullRequestSnapshot:
    return PullRequestSnapshot(
        repository="octocat/norn-agents",
        pr_number=7,
        title="t",
        body="",
        author="junior-dev",
        html_url="",
        head_sha="aaa1234",
        base_sha="bbb5678",
        head_ref="feat/sample",
        base_ref="main",
        files=[
            ChangedFile(
                path="src/sample.py",
                status="added",
                additions=2,
                deletions=0,
                patch="@@ -0,0 +1,2 @@\n+import os\n+x = 1\n",
            )
        ],
        commits=[CommitInfo(sha="aaa1234", message="add sample", author="junior-dev")],
    )


async def test_build_review_context_uses_snapshot_and_runs_ruff(
    fake_github_client, snap_with_py_file
) -> None:
    fake_github_client.set_snapshot(snap_with_py_file)
    fake_github_client.file_contents[("octocat/norn-agents", "src/sample.py", "aaa1234")] = (
        "import os\n\nx = 1\n"
    )

    payload = {
        "repository": {"full_name": "octocat/norn-agents"},
        "pull_request": {"number": 7},
    }
    ctx = await build_review_context(fake_github_client, payload)

    assert ctx.repository == "octocat/norn-agents"
    assert ctx.pr_number == 7
    assert ctx.head_sha == "aaa1234"
    assert ctx.is_pr_context
    assert len(ctx.files) == 1
    assert ctx.files[0].path == "src/sample.py"
    # 実 Ruff が走るので F401 を検出する
    assert any(f.code == "F401" for f in ctx.ruff_findings)
    assert not ctx.ruff_truncated


async def test_build_review_context_propagates_prior_turns_and_reply(
    fake_github_client, snap_with_py_file
) -> None:
    fake_github_client.set_snapshot(snap_with_py_file)
    payload = {
        "repository": {"full_name": "octocat/norn-agents"},
        "issue": {"number": 7},
    }
    prior = [AgentTurn(agent="urd", role_label="Urd", content="prior turn")]
    ctx = await build_review_context(
        fake_github_client,
        payload,
        prior_turns=prior,
        user_reply="若手の返信です",
    )
    assert ctx.prior_turns == prior
    assert ctx.user_reply == "若手の返信です"


async def test_build_review_context_raises_when_payload_lacks_pr(fake_github_client) -> None:
    with pytest.raises(ValueError):
        await build_review_context(fake_github_client, {"repository": {"full_name": "x/y"}})


async def test_ruff_runner_truncates_when_many_python_files(fake_github_client) -> None:
    files = [
        ChangedFile(
            path=f"f{i}.py",
            status="added",
            additions=1,
            deletions=0,
            patch="@@ -0,0 +1 @@\n+x = 1\n",
        )
        for i in range(55)
    ]
    snap = PullRequestSnapshot(
        repository="octocat/norn-agents",
        pr_number=999,
        title="",
        body="",
        author="",
        html_url="",
        head_sha="hhh",
        base_sha="bbb",
        head_ref="x",
        base_ref="main",
        files=files,
        commits=[],
    )
    for f in files:
        fake_github_client.file_contents[("octocat/norn-agents", f.path, "hhh")] = "x = 1\n"

    findings, truncated = await run_ruff_on_snapshot(fake_github_client, snap)
    assert truncated is True
    assert isinstance(findings, list)


async def test_ruff_runner_handles_no_python_files(fake_github_client) -> None:
    snap = PullRequestSnapshot(
        repository="o/r",
        pr_number=1,
        title="",
        body="",
        author="",
        html_url="",
        head_sha="x",
        base_sha="y",
        head_ref="z",
        base_ref="main",
        files=[
            ChangedFile(path="README.md", status="modified", patch="@@", additions=1, deletions=0)
        ],
        commits=[],
    )
    findings, truncated = await run_ruff_on_snapshot(fake_github_client, snap)
    assert findings == []
    assert truncated is False


def test_render_pr_comment_includes_session_marker_and_link() -> None:
    output = ConsensusOutput(
        summary="ok",
        must_fix=["fix me"],
        next_pr=["next"],
        growth="grow",
        tone="encouraging",
    )
    body = render_pr_comment(output, session_id="abc-123", thread_link="http://x/chat/threads/t")
    assert body.startswith("<!-- norn:session=abc-123 -->")
    assert "fix me" in body
    assert "next" in body
    assert "http://x/chat/threads/t" in body
