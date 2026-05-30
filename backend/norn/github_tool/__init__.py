"""GitHub PR Diff 取得 + コメント投稿 + Ruff 静的解析を集約する Phase 3 のツール群。"""

from norn.github_tool.builder import NORN_COMMENT_MARKER, build_review_context
from norn.github_tool.client import GitHubClient, GitHubClientProtocol, get_github_client
from norn.github_tool.markdown import render_pr_comment
from norn.github_tool.models import PullRequestSnapshot

__all__ = [
    "NORN_COMMENT_MARKER",
    "GitHubClient",
    "GitHubClientProtocol",
    "PullRequestSnapshot",
    "build_review_context",
    "get_github_client",
    "render_pr_comment",
]
