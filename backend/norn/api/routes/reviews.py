"""HITL: pending な ReviewSession を開始 / スキップする。"""

import logging
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from norn.agents import NornOrchestrator, get_orchestrator
from norn.api.routes.github import run_pr_review_for_session
from norn.db import get_session
from norn.db.repositories import append_chat_message, load_session, mark_session_status
from norn.events import get_event_bus
from norn.github_tool import GitHubClientProtocol, get_github_client

router = APIRouter(tags=["reviews"])
logger = logging.getLogger("norn.api.routes.reviews")


class ReviewActionResponse(BaseModel):
    session_id: str
    status: str


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
