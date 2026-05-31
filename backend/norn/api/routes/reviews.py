"""HITL: pending な ReviewSession を開始 / スキップする。"""

import logging
from typing import Annotated, Literal, Self
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from norn.agents import NornOrchestrator, get_orchestrator
from norn.api.routes.github import (
    _MANUAL_APPROVAL_PROMPT,
    PendingReviewRegistration,
    build_pull_request_payload,
    register_pending_review,
    run_pr_review_for_session,
)
from norn.db import get_session, session_scope
from norn.db.repositories import (
    append_chat_message,
    get_thread_user_level,
    load_session,
    mark_session_status,
)
from norn.events import get_event_bus
from norn.github_tool import GitHubClientProtocol, get_github_client
from norn.github_tool.pr_ref import parse_pr_reference

router = APIRouter(tags=["reviews"])
logger = logging.getLogger("norn.api.routes.reviews")


class ReviewActionResponse(BaseModel):
    session_id: str
    status: str


class ManualReviewRequest(BaseModel):
    repository: str | None = Field(default=None, max_length=255)
    pr_number: int | None = Field(default=None, gt=0)
    pr_ref: str | None = Field(default=None, max_length=512)
    thread_id: str | None = Field(default=None, max_length=36)
    user_level: Literal["junior", "mid", "senior"] = Field(default="junior")

    @model_validator(mode="after")
    def validate_reference(self) -> Self:
        has_pair = self.repository is not None and self.pr_number is not None
        has_ref = bool(self.pr_ref and self.pr_ref.strip())
        if has_pair == has_ref:
            raise ValueError("provide pr_ref or both repository and pr_number")
        return self


class ManualReviewResponse(BaseModel):
    session_id: str
    thread_id: str
    status: str
    repository: str
    pr_number: int
    pr_title: str
    pr_url: str | None = None


@router.post(
    "/manual",
    response_model=ManualReviewResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_manual_review(
    payload: ManualReviewRequest,
    request: Request,
    github_client: Annotated[GitHubClientProtocol, Depends(get_github_client)],
) -> ManualReviewResponse:
    """Webhook なしで PR を承認待ちキューに登録する（チャット UI から手動レビュー）。"""

    request_id = getattr(request.state, "request_id", "-")
    try:
        repository, pr_number = parse_pr_reference(
            repository=payload.repository,
            pr_number=payload.pr_number,
            pr_ref=payload.pr_ref,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    try:
        snap = await github_client.fetch_pull_request(repository, pr_number)
    except Exception as exc:
        logger.warning(
            "manual review: failed to fetch PR repo=%s pr=%s",
            repository,
            pr_number,
            extra={"request_id": request_id},
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="failed to fetch pull request from GitHub",
        ) from exc

    thread_id = payload.thread_id or str(uuid4())
    if payload.thread_id is not None:
        async with session_scope() as session:
            owner = await get_thread_user_level(session, thread_id)
            if owner is not None and owner != payload.user_level:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"thread belongs to another user_level (owner: {owner})",
                )

    webhook_payload = build_pull_request_payload(
        repository=snap.repository,
        pr_number=snap.pr_number,
        pr_title=snap.title,
        pr_url=snap.html_url,
    )
    result = await register_pending_review(
        webhook_payload,
        request_id,
        chat_thread_id=thread_id,
        allow_reopen=True,
        approval_prompt=_MANUAL_APPROVAL_PROMPT,
        user_level=payload.user_level,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="review is already running for this pull request",
        )

    logger.info(
        "manual review registered session=%s repo=%s pr=%s",
        result.session_id,
        repository,
        pr_number,
        extra={"request_id": request_id},
    )
    return _to_manual_response(result)


@router.post(
    "/{session_id}/start",
    response_model=ReviewActionResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_review(
    session_id: str,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    background_tasks: BackgroundTasks,
    orchestrator: Annotated[NornOrchestrator, Depends(get_orchestrator)],
    github_client: Annotated[GitHubClientProtocol, Depends(get_github_client)],
) -> ReviewActionResponse:
    request_id = getattr(request.state, "request_id", "-")
    review = await load_session(session, session_id)
    if review is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session not found")
    if review.status != "pending_approval":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"session is not pending_approval (current: {review.status})",
        )
    if not isinstance(review.payload_json, dict):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="session has no stored webhook payload",
        )

    background_tasks.add_task(
        run_pr_review_for_session,
        orchestrator,
        github_client,
        session_id,
        request_id,
    )
    logger.info(
        "review start dispatched session=%s pr=%s",
        session_id,
        review.pr_number,
        extra={"request_id": request_id},
    )
    return ReviewActionResponse(session_id=session_id, status="running")


@router.post(
    "/{session_id}/skip",
    response_model=ReviewActionResponse,
    status_code=status.HTTP_200_OK,
)
async def skip_review(
    session_id: str,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ReviewActionResponse:
    request_id = getattr(request.state, "request_id", "-")
    review = await load_session(session, session_id)
    if review is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session not found")
    if review.status != "pending_approval":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"session is not pending_approval (current: {review.status})",
        )

    await mark_session_status(session, session_id, "skipped")
    await append_chat_message(
        session,
        thread_id=review.chat_thread_id,
        role="assistant",
        content="今回はスキップしました。次の Draft PR でお会いしましょう。",
        user_level=await get_thread_user_level(session, review.chat_thread_id) or "junior",
    )
    await session.commit()

    bus = get_event_bus()
    await bus.publish(
        review.chat_thread_id,
        {"type": "review_skipped", "session_id": session_id},
    )
    logger.info(
        "review skipped session=%s pr=%s",
        session_id,
        review.pr_number,
        extra={"request_id": request_id},
    )
    return ReviewActionResponse(session_id=session_id, status="skipped")


def _to_manual_response(result: PendingReviewRegistration) -> ManualReviewResponse:
    return ManualReviewResponse(
        session_id=result.session_id,
        thread_id=result.thread_id,
        status=result.status,
        repository=result.repository,
        pr_number=result.pr_number,
        pr_title=result.pr_title,
        pr_url=result.pr_url,
    )
