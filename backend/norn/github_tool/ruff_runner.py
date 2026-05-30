"""PR の Python ファイル 1 群に対して Ruff を走らせ、Finding を抽出する。

戦略: PyGithub から各ファイルの head_sha 時点の内容を取得し、tempdir にミラーして
`ruff check --output-format=json` をかける。差分のみリントしないのは
F401（未使用 import）のような全文必要なルールを正しく評価するため。
"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from norn.agents.schemas import RuffFinding
from norn.config import get_settings

if TYPE_CHECKING:
    from norn.agents.schemas import ChangedFile
    from norn.github_tool.client import GitHubClientProtocol
    from norn.github_tool.models import PullRequestSnapshot

logger = logging.getLogger("norn.github_tool.ruff_runner")

_MAX_FILES_FOR_RUFF = 50
_RUFF_TIMEOUT_SECONDS = 30


async def run_ruff_on_snapshot(
    client: GitHubClientProtocol, snap: PullRequestSnapshot
) -> tuple[list[RuffFinding], bool]:
    """戻り値: (findings, truncated)。失敗時は ([], False)。"""

    py_files = [
        f
        for f in snap.files
        if f.path.endswith(".py") and f.status != "removed" and f.patch is not None
    ]
    if not py_files:
        return [], False

    truncated = False
    if len(py_files) > _MAX_FILES_FOR_RUFF:
        py_files = py_files[:_MAX_FILES_FOR_RUFF]
        truncated = True

    contents = await _fetch_contents(client, snap, py_files)
    if not contents:
        return [], truncated

    return await asyncio.to_thread(_run_ruff_sync, contents), truncated


async def _fetch_contents(
    client: GitHubClientProtocol,
    snap: PullRequestSnapshot,
    files: list[ChangedFile],
) -> dict[str, str]:
    """ファイルごとに head_sha の内容を取得。失敗したものはスキップ。"""

    result: dict[str, str] = {}
    for f in files:
        text = await client.get_file_contents(snap.repository, f.path, snap.head_sha)
        if text is not None:
            result[f.path] = text
    return result


def _run_ruff_sync(contents: dict[str, str]) -> list[RuffFinding]:
    settings = get_settings()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for relpath, body in contents.items():
            target = root / relpath
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(body, encoding="utf-8")
        try:
            proc = subprocess.run(  # noqa: S603
                [settings.ruff_executable, "check", "--output-format=json", str(root)],
                capture_output=True,
                text=True,
                timeout=_RUFF_TIMEOUT_SECONDS,
                check=False,
                shell=False,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            logger.warning("ruff invocation failed: %s", exc)
            return []

        stdout = proc.stdout or "[]"
        try:
            raw = json.loads(stdout)
        except json.JSONDecodeError as exc:
            logger.warning("ruff output is not valid JSON: %s", exc)
            return []

        findings: list[RuffFinding] = []
        for item in raw:
            filename = item.get("filename", "")
            try:
                rel = str(Path(filename).relative_to(root))
            except ValueError:
                rel = filename
            location = item.get("location") or {}
            findings.append(
                RuffFinding(
                    file=rel,
                    line=int(location.get("row", 0) or 0),
                    code=str(item.get("code") or ""),
                    message=str(item.get("message") or ""),
                )
            )
        return findings
