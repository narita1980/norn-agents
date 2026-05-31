"""GitHub PR 参照文字列のパース。"""

from __future__ import annotations

import re

_GH_PR_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/pull/(?P<number>\d+)",
    re.IGNORECASE,
)
_REPO_PR_RE = re.compile(
    r"^(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+)\s*#\s*(?P<number>\d+)\s*$"
)


def parse_pr_reference(
    *,
    repository: str | None = None,
    pr_number: int | None = None,
    pr_ref: str | None = None,
) -> tuple[str, int]:
    """`owner/repo` + PR 番号、または GitHub PR URL / `owner/repo#123` 形式を正規化する。"""

    if pr_ref:
        pr_ref = pr_ref.strip()
        if not pr_ref:
            raise ValueError("pr_ref is empty")

        url_match = _GH_PR_URL_RE.search(pr_ref)
        if url_match:
            owner = url_match.group("owner")
            repo = url_match.group("repo")
            number = int(url_match.group("number"))
            return f"{owner}/{repo}", number

        short_match = _REPO_PR_RE.match(pr_ref)
        if short_match:
            owner = short_match.group("owner")
            repo = short_match.group("repo")
            number = int(short_match.group("number"))
            return f"{owner}/{repo}", number

        raise ValueError(
            "pr_ref must be a GitHub PR URL or owner/repo#number (e.g. octocat/hello-world#42)"
        )

    if repository and pr_number is not None:
        repo = repository.strip().strip("/")
        if "/" not in repo:
            raise ValueError("repository must be owner/repo")
        if pr_number <= 0:
            raise ValueError("pr_number must be positive")
        return repo, pr_number

    raise ValueError("provide pr_ref or both repository and pr_number")
