import logging
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Request, Response, status

from norn.agents import NornOrchestrator, get_orchestrator
from norn.api.dependencies import verified_github_payload
from norn.config import get_settings
from norn.db import session_scope
from norn.db.repositories import (
    append_agent_turns,
    find_session_by_pr,
    get_or_create_review_session,
    load_prior_turns,
    mark_session_status,
)
from norn.github_tool import (
    NORN_COMMENT_MARKER,
    GitHubClientProtocol,
    build_review_context,
    get_github_client,
    render_pr_comment,
)
from norn.github_tool.markdown import render_failure_comment

router = APIRouter(tags=["github"])
logger = logging.getLogger("norn.api.routes.github")

SUPPORTED_EVENTS = {"ping", "pull_request", "issue_comment"}


@router.post("/github")
async def github_webhook(
    request: Request,
    payload: Annotated[dict[str, Any], Depends(verified_github_payload)],
    background_tasks: BackgroundTasks,
    orchestrator: Annotated[NornOrchestrator, Depends(get_orchestrator)],
    github_client: Annotated[GitHubClientProtocol, Depends(get_github_client)],
    x_github_event: Annotated[str | None, Header(alias="X-GitHub-Event")] = None,
    x_github_delivery: Annotated[str | None, Header(alias="X-GitHub-Delivery")] = None,
) -> Response:
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
        _handle_pull_request_event(
            payload, background_tasks, orchestrator, github_client, request_id
        )
    elif x_github_event == "issue_comment":
        _handle_comment_event(payload, background_tasks, orchestrator, github_client, request_id)

    return Response(
        status_code=status.HTTP_202_ACCEPTED,
        content='{"accepted": true}',
        media_type="application/json",
    )


def _handle_pull_request_event(
    payload: dict[str, Any],
    background_tasks: BackgroundTasks,
    orchestrator: NornOrchestrator,
    github_client: GitHubClientProtocol,
    request_id: str,
) -> None:
    action = payload.get("action")
    pull_request = payload.get("pull_request", {})
    pr_number = pull_request.get("number")
    is_draft = bool(pull_request.get("draft", False))
    if action == "opened" and is_draft:
        logger.info(
            "draft PR opened pr=%s — dispatching agents",
            pr_number,
            extra={"request_id": request_id},
        )
        background_tasks.add_task(
            _run_pr_review,
            orchestrator,
            github_client,
            payload,
            request_id,
        )
    else:
        logger.info(
            "pull_request event ignored action=%s draft=%s pr=%s",
            action,
            is_draft,
            pr_number,
            extra={"request_id": request_id},
        )


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


async def _run_pr_review(
    orchestrator: NornOrchestrator,
    github_client: GitHubClientProtocol,
    payload: dict[str, Any],
    request_id: str,
) -> None:
    repo = payload.get("repository", {}).get("full_name", "?")
    pr_number = payload.get("pull_request", {}).get("number")
    if pr_number is None:
        logger.warning("PR review skipped: no pr_number repo=%s", repo)
        return

    settings = get_settings()
    async with session_scope() as session:
        review_session = await get_or_create_review_session(
            session, repository_name=repo, pr_number=pr_number
        )
        await session.commit()

        try:
            context = await build_review_context(github_client, payload)
            result = await orchestrator.run(context)

            await append_agent_turns(session, review_session.id, result.transcript)
            await session.commit()

            thread_link = (
                f"{settings.norn_app_base_url.rstrip('/')}"
                f"/chat/threads/{review_session.chat_thread_id}"
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
                    "PR comment post failed pr=%s",
                    pr_number,
                    extra={"request_id": request_id},
                )

            await mark_session_status(session, review_session.id, "completed")
            await session.commit()

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
            await mark_session_status(session, review_session.id, "failed")
            await session.commit()
            try:
                await github_client.post_issue_comment(
                    repo, pr_number, render_failure_comment(session_id=review_session.id)
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
        try:
            context = await build_review_context(
                github_client, payload, prior_turns=prior_turns, user_reply=user_reply
            )
            result = await orchestrator.run(context)
            await append_agent_turns(session, review_session.id, result.transcript)
            await session.commit()

            thread_link = (
                f"{settings.norn_app_base_url.rstrip('/')}"
                f"/chat/threads/{review_session.chat_thread_id}"
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
