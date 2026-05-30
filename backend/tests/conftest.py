import hashlib
import hmac
import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from norn.agents import (
    ConsensusOutput,
    NornOrchestrator,
    ReviewContext,
)
from norn.agents.orchestrator import get_orchestrator
from norn.agents.schemas import AgentTurn, ChangedFile, CommitInfo, ConsensusResult, RuffFinding
from norn.api.main import create_app
from norn.config import Settings
from norn.db.engine import reset_engine_cache
from norn.github_tool import get_github_client
from norn.github_tool.client import GitHubClientProtocol
from norn.github_tool.models import PullRequestSnapshot

FIXTURES_DIR = Path(__file__).parent / "fixtures"

TEST_GITHUB_SECRET = "testsecret"


@pytest.fixture
def settings_test(tmp_path: Path) -> Settings:
    db_path = tmp_path / "norn-test.db"
    return Settings(
        github_webhook_secret=TEST_GITHUB_SECRET,
        github_token="test-token",
        azure_openai_api_key="dummy",
        azure_openai_endpoint="https://dummy.openai.azure.com",
        azure_openai_deployment="dummy-deployment",
        database_url=f"sqlite+aiosqlite:///{db_path}",
        norn_app_base_url="http://testserver",
        log_level="WARNING",
        payload_size_limit_bytes=2048,
    )


class FakeOrchestrator(NornOrchestrator):
    def __init__(self, result: ConsensusResult) -> None:
        self._result = result
        self.calls: list[ReviewContext] = []

    async def run(self, context: ReviewContext) -> ConsensusResult:
        self.calls.append(context)
        return self._result


class FakeGitHubClient:
    """テスト用フェイク GitHub クライアント。"""

    def __init__(self) -> None:
        self.snapshots: dict[tuple[str, int], PullRequestSnapshot] = {}
        self.file_contents: dict[tuple[str, str, str], str | None] = {}
        self.posted_comments: list[tuple[str, int, str]] = []
        self.next_comment_id = 1000

    def set_snapshot(self, snapshot: PullRequestSnapshot) -> None:
        self.snapshots[(snapshot.repository, snapshot.pr_number)] = snapshot

    async def fetch_pull_request(self, repository: str, pr_number: int) -> PullRequestSnapshot:
        key = (repository, pr_number)
        if key in self.snapshots:
            return self.snapshots[key]
        return PullRequestSnapshot(
            repository=repository,
            pr_number=pr_number,
            title="(fake) sample PR",
            body="",
            author="junior-dev",
            html_url=f"https://github.com/{repository}/pull/{pr_number}",
            head_sha="abc1234",
            base_sha="def4567",
            head_ref="feat/sample",
            base_ref="main",
            files=[],
            commits=[],
        )

    async def post_issue_comment(self, repository: str, pr_number: int, body: str) -> int:
        self.posted_comments.append((repository, pr_number, body))
        comment_id = self.next_comment_id
        self.next_comment_id += 1
        return comment_id

    async def get_file_contents(self, repository: str, path: str, ref: str) -> str | None:
        return self.file_contents.get((repository, path, ref))


def _default_consensus_result() -> ConsensusResult:
    output = ConsensusOutput(
        summary="動く実装まで持ってきていて素晴らしいです。",
        must_fix=["入力 None のときの分岐を追加してください"],
        next_pr=["関数を 30 行以下に分割しましょう"],
        growth="次は契約による設計（DbC）に触れると一段上がれます。",
        tone="encouraging",
    )
    transcript = [
        AgentTurn(agent="urd", role_label="Urd（技術）", content="None 分岐がない"),
        AgentTurn(
            agent="verdandi", role_label="Verdandi（共感・現在）", content="まず動かしたのがすごい"
        ),
        AgentTurn(agent="skuld", role_label="Skuld（未来・成長）", content="DbC を学ぼう"),
        AgentTurn(
            agent="moderator", role_label="Consensus Moderator", content=output.model_dump_json()
        ),
    ]
    return ConsensusResult(output=output, transcript=transcript)


@pytest.fixture
def fake_orchestrator() -> FakeOrchestrator:
    return FakeOrchestrator(_default_consensus_result())


@pytest.fixture
def fake_github_client() -> FakeGitHubClient:
    client = FakeGitHubClient()
    client.set_snapshot(
        PullRequestSnapshot(
            repository="octocat/norn-agents",
            pr_number=42,
            title="feat: add user profile endpoint",
            body="",
            author="junior-dev",
            html_url="https://github.com/octocat/norn-agents/pull/42",
            head_sha="abc1234",
            base_sha="def4567",
            head_ref="feat/user-profile",
            base_ref="main",
            files=[
                ChangedFile(
                    path="src/profile.py",
                    status="added",
                    additions=10,
                    deletions=0,
                    patch="@@ -0,0 +1,10 @@\n+def hello():\n+    return 'hi'",
                )
            ],
            commits=[CommitInfo(sha="abc1234", message="add profile", author="junior-dev")],
        )
    )
    return client


@pytest.fixture
def app(
    settings_test: Settings,
    fake_orchestrator: FakeOrchestrator,
    fake_github_client: FakeGitHubClient,
):
    reset_engine_cache()
    application = create_app(settings=settings_test)
    application.dependency_overrides[get_orchestrator] = lambda: fake_orchestrator
    application.dependency_overrides[get_github_client] = lambda: fake_github_client
    yield application
    reset_engine_cache()


@pytest.fixture
def client(app) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def github_signature():
    def _sign(body: bytes, secret: str = TEST_GITHUB_SECRET) -> str:
        digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        return f"sha256={digest}"

    return _sign


@pytest.fixture
def github_ping_payload() -> bytes:
    return (FIXTURES_DIR / "github_ping.json").read_bytes()


@pytest.fixture
def github_pull_request_payload() -> bytes:
    return (FIXTURES_DIR / "github_pull_request.json").read_bytes()


@pytest.fixture
def github_pull_request_non_draft_payload() -> bytes:
    return (FIXTURES_DIR / "github_pull_request_non_draft.json").read_bytes()


@pytest.fixture
def github_issue_comment_payload() -> bytes:
    return (FIXTURES_DIR / "github_issue_comment.json").read_bytes()


@pytest.fixture
def github_issue_comment_norn_payload() -> bytes:
    return (FIXTURES_DIR / "github_issue_comment_norn.json").read_bytes()


@pytest.fixture
def parsed_pull_request(github_pull_request_payload: bytes) -> dict:
    return json.loads(github_pull_request_payload)


@pytest.fixture
def review_context_fixture() -> ReviewContext:
    """ペルソナ/オーケストレータ単体テスト用の最小 ReviewContext。"""

    return ReviewContext(
        user_input="",
        repository="octocat/norn-agents",
        pr_number=42,
        pr_title="feat: add profile",
        head_sha="abc1234",
        base_sha="def4567",
        head_ref="feat/profile",
        base_ref="main",
        files=[
            ChangedFile(
                path="src/profile.py",
                status="added",
                additions=10,
                deletions=0,
                patch="@@ -0,0 +1,3 @@\n+def hello():\n+    return 'hi'",
            )
        ],
        commits=[CommitInfo(sha="abc1234def", message="add profile", author="junior-dev")],
        ruff_findings=[
            RuffFinding(file="src/profile.py", line=1, code="F401", message="unused import")
        ],
    )


def _is_protocol(client: object) -> bool:
    return isinstance(client, GitHubClientProtocol)
