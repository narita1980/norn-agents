"""GitHub API クライアント。PyGithub は同期なので asyncio.to_thread で逃がす。"""

from __future__ import annotations

import asyncio
import logging
from typing import Annotated, Protocol

from fastapi import Depends
from github import Github, GithubException
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from norn.agents.schemas import ChangedFile, CommitInfo
from norn.config import Settings, get_settings
from norn.github_tool.models import PullRequestSnapshot

logger = logging.getLogger("norn.github_tool.client")

_MAX_FILES = 200
_MAX_COMMITS = 50


class GitHubClientProtocol(Protocol):
    async def fetch_pull_request(self, repository: str, pr_number: int) -> PullRequestSnapshot: ...

    async def post_issue_comment(self, repository: str, pr_number: int, body: str) -> int: ...

    async def get_file_contents(self, repository: str, path: str, ref: str) -> str | None: ...


class GitHubClient:
    """PyGithub の薄いラッパー。テスト時は `dependency_overrides` で差し替える。"""

    def __init__(self, token: str) -> None:
        if not token:
            raise ValueError("GITHUB_TOKEN is required to use GitHubClient")
        self._client = Github(login_or_token=token)

    @retry(
        retry=retry_if_exception_type(GithubException),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def fetch_pull_request(self, repository: str, pr_number: int) -> PullRequestSnapshot:
        return await asyncio.to_thread(self._fetch_pr_sync, repository, pr_number)

    def _fetch_pr_sync(self, repository: str, pr_number: int) -> PullRequestSnapshot:
        repo = self._client.get_repo(repository)
        pr = repo.get_pull(pr_number)

        files: list[ChangedFile] = []
        for f in pr.get_files()[:_MAX_FILES]:
            files.append(
                ChangedFile(
                    path=f.filename,
                    status=f.status,
                    additions=f.additions,
                    deletions=f.deletions,
                    patch=getattr(f, "patch", None),
                )
            )

        commits: list[CommitInfo] = []
        for c in pr.get_commits()[:_MAX_COMMITS]:
            commits.append(
                CommitInfo(
                    sha=c.sha,
                    message=c.commit.message,
                    author=(c.commit.author.name if c.commit.author else "") or "",
                )
            )

        return PullRequestSnapshot(
            repository=repository,
            pr_number=pr_number,
            title=pr.title or "",
            body=pr.body or "",
            author=pr.user.login if pr.user else "",
            html_url=pr.html_url or "",
            head_sha=pr.head.sha or "",
            base_sha=pr.base.sha or "",
            head_ref=pr.head.ref or "",
            base_ref=pr.base.ref or "",
            files=files,
            commits=commits,
        )

    @retry(
        retry=retry_if_exception_type(GithubException),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def post_issue_comment(self, repository: str, pr_number: int, body: str) -> int:
        return await asyncio.to_thread(self._post_comment_sync, repository, pr_number, body)

    def _post_comment_sync(self, repository: str, pr_number: int, body: str) -> int:
        repo = self._client.get_repo(repository)
        issue = repo.get_issue(pr_number)
        comment = issue.create_comment(body)
        return comment.id

    async def get_file_contents(self, repository: str, path: str, ref: str) -> str | None:
        try:
            return await asyncio.to_thread(self._get_contents_sync, repository, path, ref)
        except GithubException as exc:
            logger.warning(
                "failed to fetch contents repo=%s path=%s ref=%s status=%s",
                repository,
                path,
                ref,
                getattr(exc, "status", "?"),
            )
            return None

    def _get_contents_sync(self, repository: str, path: str, ref: str) -> str | None:
        repo = self._client.get_repo(repository)
        contents = repo.get_contents(path, ref=ref)
        if isinstance(contents, list):
            return None
        try:
            return contents.decoded_content.decode("utf-8")
        except (UnicodeDecodeError, AttributeError):
            return None


def get_github_client(
    settings: Annotated[Settings, Depends(get_settings)],
) -> GitHubClient:
    """FastAPI Depends 用ファクトリ。テストでは override する。"""

    return build_github_client(settings)


def build_github_client(settings: Settings | None = None) -> GitHubClient:
    """リクエスト外（Webhook ハンドラ等）から GitHub クライアントを構築する。"""

    settings = settings or get_settings()
    token = settings.github_token or ""
    return GitHubClient(token)
