import logging
from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Request, Response, status

from norn.agents import NornOrchestrator, get_orchestrator
from norn.agents.schemas import UserLevel
from norn.api.dependencies import verified_github_payload
from norn.config import get_settings
from norn.db import session_scope
from norn.db.repositories import (
    append_agent_turns,
    append_chat_message,
    find_session_by_pr,
    get_or_create_review_session,
    get_thread_user_level,
    load_prior_turns,
    load_session,
    mark_session_status,
    set_session_payload,
)
from norn.events import get_event_bus
from norn.github_tool import (
    NORN_COMMENT_MARKER,
    GitHubClientProtocol,
    build_github_client,
    build_review_context,
    render_pr_comment,
)
from norn.github_tool.markdown import render_failure_comment

router = APIRouter(tags=["github"])
logger = logging.getLogger("norn.api.routes.github")

SUPPORTED_EVENTS = {"ping", "pull_request", "issue_comment"}

_APPROVAL_PROMPT = (
    "Draft PR を受け取りました。Norn のレビューを開始しますか？\n"
    "（開始するとウルド・ヴェルダンディ・スクルドの 3 女神が合議し、GitHub にコメントを残します）"
)

_MANUAL_APPROVAL_PROMPT = (
    "プルリクエストを手動で登録しました。Norn のレビューを開始しますか？\n"
    "（開始するとウルド・ヴェルダンディ・スクルドの 3 女神が合議し、GitHub にコメントを残します）"
)


@dataclass(slots=True)
class PendingReviewRegistration:
    session_id: str
    thread_id: str
    repository: str
    pr_number: int
    pr_title: str
    pr_url: str | None
    status: str


def build_pull_request_payload(
    *,
    repository: str,
    pr_number: int,
    pr_title: str,
    pr_url: str,
) -> dict[str, Any]:
    return {
        "repository": {"full_name": repository},
        "pull_request": {
            "number": pr_number,
            "title": pr_title,
            "html_url": pr_url,
        },
    }


async def register_pending_review(
    payload: dict[str, Any],
    request_id: str,
    *,
    chat_thread_id: str | None = None,
    allow_reopen: bool = False,
    approval_prompt: str = _APPROVAL_PROMPT,
    user_level: UserLevel = "junior",
) -> PendingReviewRegistration | None:
    """ReviewSession を `pending_approval` で登録し、Start/Skip プロンプトを書き込む。"""

    repo = payload.get("repository", {}).get("full_name", "?")
    pull_request = payload.get("pull_request", {})
    pr_number = pull_request.get("number")
    if pr_number is None:
        logger.warning("pending review skipped: no pr_number repo=%s", repo)
        return None

    pr_title = pull_request.get("title") or ""
    pr_url = pull_request.get("html_url")

    async with session_scope() as session:
        review_session = await get_or_create_review_session(
            session,
            repository_name=repo,
            pr_number=pr_number,
            chat_thread_id=chat_thread_id,
        )
        if review_session.status == "running":
            logger.info(
                "pending review skipped: already running pr=%s",
                pr_number,
                extra={"request_id": request_id},
            )
            return None

        if review_session.status == "pending_approval":
            return PendingReviewRegistration(
                session_id=review_session.id,
                thread_id=review_session.chat_thread_id,
                repository=repo,
                pr_number=pr_number,
                pr_title=pr_title,
                pr_url=pr_url,
                status=review_session.status,
            )

        if not allow_reopen and review_session.status not in {"skipped"}:
            logger.info(
                "pending review skipped: already %s pr=%s",
                review_session.status,
                pr_number,
                extra={"request_id": request_id},
            )
            return None

        review_session.status = "pending_approval"
        await set_session_payload(session, review_session.id, payload)

        action_payload = {
            "type": "start_or_skip",
            "session_id": review_session.id,
            "repository": repo,
            "pr_number": pr_number,
            "pr_title": pr_title,
            "pr_url": pr_url,
        }
        content = f"**{repo} #{pr_number}** {pr_title}\n\n{approval_prompt}"
        await append_chat_message(
            session,
            thread_id=review_session.chat_thread_id,
            role="assistant",
            content=content,
            action_payload=action_payload,
            user_level=user_level,
        )
        await session.commit()

    bus = get_event_bus()
    await bus.publish(
        review_session.chat_thread_id,
        {
            "type": "review_pending",
            "session_id": review_session.id,
            "repository": repo,
            "pr_number": pr_number,
            "pr_title": pr_title,
        },
    )
    return PendingReviewRegistration(
        session_id=review_session.id,
        thread_id=review_session.chat_thread_id,
        repository=repo,
        pr_number=pr_number,
        pr_title=pr_title,
        pr_url=pr_url,
        status="pending_approval",
    )


@router.post("/github")
async def github_webhook(
    request: Request,
    payload: Annotated[dict[str, Any], Depends(verified_github_payload)],
    background_tasks: BackgroundTasks,
    x_github_event: Annotated[str | None, Header(alias="X-GitHub-Event")] = None,
    x_github_delivery: Annotated[str | None, Header(alias="X-GitHub-Delivery")] = None,
) -> Response:
    """Pull Request opened は orchestrator を呼ばずに pending を登録するだけ。
    orchestrator / GitHub クライアントは issue_comment 経路でのみ遅延解決する。
    """

    request_id = getattr(request.state, "request_id", "-")
    logger.info(
        "github webhook received event=%s delivery=%s repo=%s",
        x_github_event,
        x_github_delivery,
        payload.get("repository", {}).get("full_name"),
        extra={"request_id": request_id},
    )

    if x_github_event == "ping":
        return Response(
            status_code=status.HTTP_200_OK,
            content='{"pong": true}',
            media_type="application/json",
        )

    if x_github_event not in SUPPORTED_EVENTS:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    if x_github_event == "pull_request":
        await _handle_pull_request_event(payload, request_id)
    elif x_github_event == "issue_comment":
        _handle_comment_event(
            payload,
            background_tasks,
            get_orchestrator(),
            build_github_client(),
            request_id,
        )

    return Response(
        status_code=status.HTTP_202_ACCEPTED,
        content='{"accepted": true}',
        media_type="application/json",
    )


async def _handle_pull_request_event(
    payload: dict[str, Any],
    request_id: str,
) -> None:
    """Phase 4 から自動発火を停止。Draft PR opened は pending 状態で記録するのみ。"""

    action = payload.get("action")
    pull_request = payload.get("pull_request", {})
    pr_number = pull_request.get("number")
    is_draft = bool(pull_request.get("draft", False))
    if action == "opened" and is_draft:
        logger.info(
            "draft PR opened pr=%s — creating pending review (HITL)",
            pr_number,
            extra={"request_id": request_id},
        )
        await _create_pending_review(payload, request_id)
    else:
        logger.info(
            "pull_request event ignored action=%s draft=%s pr=%s",
            action,
            is_draft,
            pr_number,
            extra={"request_id": request_id},
        )


async def _create_pending_review(payload: dict[str, Any], request_id: str) -> None:
    """Webhook 経由の Draft PR opened。再送時は skipped のみ再登録可能。"""

    await register_pending_review(payload, request_id, allow_reopen=False)


def _handle_comment_event(
    payload: dict[str, Any],
    background_tasks: BackgroundTasks,
    orchestrator: NornOrchestrator,
    github_client: GitHubClientProtocol,
    request_id: str,
) -> None:
    action = payload.get("action")
    comment = payload.get("comment", {}) or {}
    issue = payload.get("issue", {}) or {}
    repo = payload.get("repository", {}).get("full_name")
    pr_number = issue.get("number")

    is_pr_comment = "pull_request" in issue
    if not is_pr_comment:
        logger.info(
            "issue_comment ignored: not on a PR repo=%s issue=%s",
            repo,
            pr_number,
            extra={"request_id": request_id},
        )
        return

    if action != "created":
        logger.info(
            "issue_comment ignored action=%s pr=%s",
            action,
            pr_number,
            extra={"request_id": request_id},
        )
        return

    body = comment.get("body") or ""
    if NORN_COMMENT_MARKER in body:
        logger.info(
            "issue_comment ignored: norn marker present pr=%s",
            pr_number,
            extra={"request_id": request_id},
        )
        return

    logger.info(
        "comment received pr=%s author=%s — dispatching reply consensus",
        pr_number,
        comment.get("user", {}).get("login"),
        extra={"request_id": request_id},
    )
    background_tasks.add_task(
        _run_pr_reply,
        orchestrator,
        github_client,
        payload,
        body,
        request_id,
    )


async def run_pr_review_for_session(
    orchestrator: NornOrchestrator,
    github_client: GitHubClientProtocol,
    session_id: str,
    request_id: str,
) -> None:
    """`/reviews/{id}/start` から呼ばれる本体。session の payload_json を再生する。

    `_handle_pull_request_event` から直接呼ばれることは無いが、テスト・運用上の
    再投入経路にもなる（status を pending_approval に戻して再起動可能）。
    """

    settings = get_settings()
    bus = get_event_bus()

    async with session_scope() as session:
        review_session = await load_session(session, session_id)
        if review_session is None:
            logger.warning("review dispatch: session not found id=%s", session_id)
            return
        payload = review_session.payload_json
        if not isinstance(payload, dict):
            logger.warning(
                "review dispatch: no payload stored session=%s pr=%s",
                session_id,
                review_session.pr_number,
            )
            await mark_session_status(session, session_id, "failed")
            await session.commit()
            return

        review_session.status = "running"
        await session.commit()
        thread_id = review_session.chat_thread_id
        repo = review_session.repository_name
        pr_number = review_session.pr_number

        await bus.publish(
            thread_id,
            {"type": "review_started", "session_id": session_id, "pr_number": pr_number},
        )

        async def publisher(event: dict[str, Any]) -> None:
            await bus.publish(thread_id, event)

        try:
            context = await build_review_context(github_client, payload)
            result = await orchestrator.run(context, on_event=publisher)

            await append_agent_turns(session, session_id, result.transcript)
            thread_level = await get_thread_user_level(session, thread_id) or "junior"
            await append_chat_message(
                session,
                thread_id=thread_id,
                role="assistant",
                content=_render_reply_text(result.output),
                consensus=result.output.model_dump(),
                transcript=[turn.model_dump() for turn in result.transcript],
                user_level=thread_level,
            )
            await session.commit()

            thread_link = (
                f"{settings.norn_app_base_url.rstrip('/')}"
                f"/chat/threads/{thread_id}"
            )
            comment_body = render_pr_comment(
                result.output,
                session_id=session_id,
                thread_link=thread_link,
            )
            try:
                await github_client.post_issue_comment(repo, pr_number, comment_body)
            except Exception:
                logger.exception(
                    "PR comment post failed pr=%s",
                    pr_number,
                    extra={"request_id": request_id},
                )

            await mark_session_status(session, session_id, "completed")
            await session.commit()
            await bus.publish(
                thread_id,
                {
                    "type": "review_completed",
                    "session_id": session_id,
                    "consensus": result.output.model_dump(),
                },
            )

            logger.info(
                "agent consensus ready pr=%s tone=%s must_fix=%d next_pr=%d",
                pr_number,
                result.output.tone,
                len(result.output.must_fix),
                len(result.output.next_pr),
                extra={"request_id": request_id},
            )
        except Exception:
            logger.exception(
                "agent dispatch failed pr=%s",
                pr_number,
                extra={"request_id": request_id},
            )
            await mark_session_status(session, session_id, "failed")
            await session.commit()
            await bus.publish(
                thread_id,
                {"type": "review_failed", "session_id": session_id},
            )
            try:
                await github_client.post_issue_comment(
                    repo, pr_number, render_failure_comment(session_id=session_id)
                )
            except Exception:
                logger.exception(
                    "failure-notice post also failed pr=%s",
                    pr_number,
                    extra={"request_id": request_id},
                )


async def _run_pr_reply(
    orchestrator: NornOrchestrator,
    github_client: GitHubClientProtocol,
    payload: dict[str, Any],
    user_reply: str,
    request_id: str,
) -> None:
    repo = payload.get("repository", {}).get("full_name", "?")
    pr_number = payload.get("issue", {}).get("number")
    if pr_number is None:
        return

    settings = get_settings()
    bus = get_event_bus()
    async with session_scope() as session:
        review_session = await find_session_by_pr(
            session, repository_name=repo, pr_number=pr_number
        )
        if review_session is None:
            logger.warning(
                "comment on unknown PR repo=%s pr=%s",
                repo,
                pr_number,
                extra={"request_id": request_id},
            )
            return

        prior_turns = await load_prior_turns(session, review_session.id)
        thread_id = review_session.chat_thread_id

        async def publisher(event: dict[str, Any]) -> None:
            await bus.publish(thread_id, event)

        try:
            context = await build_review_context(
                github_client, payload, prior_turns=prior_turns, user_reply=user_reply
            )
            result = await orchestrator.run(context, on_event=publisher)
            await append_agent_turns(session, review_session.id, result.transcript)
            thread_level = await get_thread_user_level(session, thread_id) or "junior"
            await append_chat_message(
                session,
                thread_id=thread_id,
                role="assistant",
                content=_render_reply_text(result.output),
                consensus=result.output.model_dump(),
                transcript=[turn.model_dump() for turn in result.transcript],
                user_level=thread_level,
            )
            await session.commit()

            thread_link = (
                f"{settings.norn_app_base_url.rstrip('/')}"
                f"/chat/threads/{thread_id}"
            )
            comment_body = render_pr_comment(
                result.output,
                session_id=review_session.id,
                thread_link=thread_link,
            )
            try:
                await github_client.post_issue_comment(repo, pr_number, comment_body)
            except Exception:
                logger.exception(
                    "PR reply post failed pr=%s",
                    pr_number,
                    extra={"request_id": request_id},
                )

            await bus.publish(
                thread_id,
                {
                    "type": "review_completed",
                    "session_id": review_session.id,
                    "consensus": result.output.model_dump(),
                },
            )

            logger.info(
                "agent reply consensus ready pr=%s tone=%s",
                pr_number,
                result.output.tone,
                extra={"request_id": request_id},
            )
        except Exception:
            logger.exception(
                "agent reply dispatch failed pr=%s",
                pr_number,
                extra={"request_id": request_id},
            )
            await bus.publish(
                thread_id,
                {"type": "review_failed", "session_id": review_session.id},
            )


def _render_reply_text(output: Any) -> str:
    """ConsensusOutput を assistant メッセージ用のプレーンテキストに整形。

    chat.py の `_render_reply` と一致した出力を保つため、こちらも同形式で揃える。
    （chat.py 側のヘルパに依存させると循環 import になりやすいので関数を複製）
    """

    lines = [output.summary.strip()]
    if output.must_fix:
        lines.append("\n**いま直したいこと**")
        lines.extend(f"- {item}" for item in output.must_fix)
    if output.next_pr:
        lines.append("\n**次の PR で**")
        lines.extend(f"- {item}" for item in output.next_pr)
    if output.growth:
        lines.append("\n**成長機会**")
        lines.append(output.growth.strip())
    return "\n".join(lines)
