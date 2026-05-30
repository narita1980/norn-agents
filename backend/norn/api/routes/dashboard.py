"""シニア向け『組織の成長ダッシュボード』モック API。

実 DB 統計（セッション件数 / tone 分布 / 最近完了したセッション）に、
シンプルな前提に基づくモック KPI（削減工数 / 平均指摘数 等）を合成して返す。
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from norn.db import get_session
from norn.db.repositories import (
    aggregate_session_stats,
    recent_completed_sessions,
)

router = APIRouter(tags=["dashboard"])
logger = logging.getLogger("norn.api.routes.dashboard")

# モック KPI の前提係数。デモ用の根拠ナレーション込みでこの場で説明する。
_SENIOR_HOURS_PER_REVIEW = 0.5  # 1 PR = シニア 30 分の代替と仮定
_AVG_LEARNING_MINUTES_PER_REVIEW = 12  # 若手の学習時間プロキシ


class SessionCounts(BaseModel):
    total: int = 0
    completed: int = 0
    failed: int = 0
    skipped: int = 0
    pending: int = 0
    running: int = 0


class RecentSession(BaseModel):
    session_id: str
    repository: str
    pr_number: int
    updated_at: str | None
    status: str


class DashboardMock(BaseModel):
    estimated_senior_hours_saved: float
    learning_minutes_total: int
    completion_rate: float = Field(ge=0.0, le=1.0)


class DashboardStats(BaseModel):
    sessions: SessionCounts
    by_tone: dict[str, int]
    recent: list[RecentSession]
    mock: DashboardMock


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DashboardStats:
    stats = await aggregate_session_stats(session)
    recent = await recent_completed_sessions(session, limit=10)

    counts = SessionCounts(
        total=stats.total,
        completed=stats.by_status.get("completed", 0),
        failed=stats.by_status.get("failed", 0),
        skipped=stats.by_status.get("skipped", 0),
        pending=stats.by_status.get("pending_approval", 0),
        running=stats.by_status.get("running", 0),
    )

    decided = counts.completed + counts.skipped + counts.failed
    completion_rate = (counts.completed / decided) if decided else 0.0

    mock = DashboardMock(
        estimated_senior_hours_saved=round(counts.completed * _SENIOR_HOURS_PER_REVIEW, 2),
        learning_minutes_total=counts.completed * _AVG_LEARNING_MINUTES_PER_REVIEW,
        completion_rate=round(completion_rate, 3),
    )

    recent_models = [
        RecentSession(
            session_id=row.id,
            repository=row.repository_name,
            pr_number=row.pr_number,
            updated_at=row.updated_at.isoformat() if row.updated_at else None,
            status=row.status,
        )
        for row in recent
    ]

    return DashboardStats(
        sessions=counts,
        by_tone=stats.by_tone,
        recent=recent_models,
        mock=mock,
    )
