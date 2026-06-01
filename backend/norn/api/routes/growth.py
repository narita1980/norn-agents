"""成長プロファイル・タイムライン・フィードバック API。"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from norn.agents.growth import get_growth_timeline_for_user, resolve_user_id
from norn.agents.schemas import UserLevel
from norn.db import get_session
from norn.db.repositories import (
    adjust_agent_memory_quality,
    get_learner_profile,
    update_message_feedback,
)

router = APIRouter(tags=["growth"])


class LearnerProfileResponse(BaseModel):
    user_id: int
    skill_level: UserLevel
    growth_summary: str
    active_goals: list[str]
    resolved_topics: list[str]
    weak_areas: list[str]
    review_count: int
    updated_at: str | None


class GrowthTimelineEntry(BaseModel):
    message_id: str | None
    created_at: str | None
    growth: str
    summary: str
    tone: str


class GrowthTimelineResponse(BaseModel):
    entries: list[GrowthTimelineEntry]


class MessageFeedbackRequest(BaseModel):
    rating: Literal[-1, 1]
    user_level: UserLevel = "junior"


class MessageFeedbackResponse(BaseModel):
    ok: bool
    message_id: str


@router.get("/profile", response_model=LearnerProfileResponse)
async def get_profile(
    session: Annotated[AsyncSession, Depends(get_session)],
    user_level: UserLevel = "junior",
) -> LearnerProfileResponse:
    user_id = await resolve_user_id(session, user_level)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    profile = await get_learner_profile(session, user_id)
    if profile is None:
        return LearnerProfileResponse(
            user_id=user_id,
            skill_level=user_level,
            growth_summary="",
            active_goals=[],
            resolved_topics=[],
            weak_areas=[],
            review_count=0,
            updated_at=None,
        )
    return LearnerProfileResponse(
        user_id=user_id,
        skill_level=profile.skill_level,  # type: ignore[arg-type]
        growth_summary=profile.growth_summary or "",
        active_goals=list(profile.active_goals or []),
        resolved_topics=list(profile.resolved_topics or []),
        weak_areas=list(profile.weak_areas or []),
        review_count=profile.review_count,
        updated_at=profile.updated_at.isoformat() if profile.updated_at else None,
    )


@router.get("/timeline", response_model=GrowthTimelineResponse)
async def get_timeline(
    session: Annotated[AsyncSession, Depends(get_session)],
    user_level: UserLevel = "junior",
    limit: int = 20,
) -> GrowthTimelineResponse:
    user_id = await resolve_user_id(session, user_level)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    rows = await get_growth_timeline_for_user(session, user_id, limit=limit)
    return GrowthTimelineResponse(
        entries=[GrowthTimelineEntry(**row) for row in rows]
    )


@router.post(
    "/messages/{message_id}/feedback",
    response_model=MessageFeedbackResponse,
)
async def post_message_feedback(
    message_id: str,
    body: MessageFeedbackRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MessageFeedbackResponse:
    ok = await update_message_feedback(
        session,
        message_id=message_id,
        rating=body.rating,
        user_level=body.user_level,
    )
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="message not found")
    await adjust_agent_memory_quality(
        session,
        message_id=message_id,
        rating=body.rating,
        user_level=body.user_level,
    )
    await session.commit()
    return MessageFeedbackResponse(ok=True, message_id=message_id)
