import asyncio
import json
import logging
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from norn.agents import (
    AgentTurn,
    ConsensusOutput,
    NornOrchestrator,
    ReviewContext,
    get_orchestrator,
)
from norn.db import get_session
from norn.db.models import ChatMessage
from norn.db.repositories import (
    ThreadSummary,
    append_chat_message,
    list_thread_summaries,
    load_thread_messages,
)
from norn.events import get_event_bus

router = APIRouter(tags=["chat"])
logger = logging.getLogger("norn.api.routes.chat")

# SSE で send buffer に何も流れない時に keep-alive コメントを送る間隔。
_SSE_KEEPALIVE_SECONDS = 15.0


class ChatMessageRequest(BaseModel):
    thread_id: str | None = Field(default=None)
    content: str = Field(min_length=1, max_length=10_000)


class ChatMessageResponse(BaseModel):
    thread_id: str
    message_id: str
    reply: str
    consensus: ConsensusOutput | None = None
    transcript: list[AgentTurn] = Field(default_factory=list)


class ChatThreadResponse(BaseModel):
    thread_id: str
    messages: list[dict[str, Any]]


class ThreadSummaryModel(BaseModel):
    thread_id: str
    last_message_at: str | None
    last_role: str | None
    last_excerpt: str
    session_id: str | None
    repository_name: str | None
    pr_number: int | None
    status: str | None
    has_pending_action: bool


class ThreadsResponse(BaseModel):
    threads: list[ThreadSummaryModel]


_AGENT_FAILURE_REPLY = (
    "申し訳ありません、合議エージェントが応答できませんでした。時間をおいて再度お試しください。"
)


@router.post("/messages", response_model=ChatMessageResponse, status_code=status.HTTP_201_CREATED)
async def post_message(
    payload: ChatMessageRequest,
    request: Request,
    orchestrator: Annotated[NornOrchestrator, Depends(get_orchestrator)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ChatMessageResponse:
    request_id = getattr(request.state, "request_id", "-")
    thread_id = payload.thread_id or str(uuid4())
    message_id = str(uuid4())

    await append_chat_message(
        session,
        thread_id=thread_id,
        role="user",
        content=payload.content,
        message_id=message_id,
    )

    bus = get_event_bus()

    async def publisher(event: dict[str, Any]) -> None:
        await bus.publish(thread_id, event)

    consensus: ConsensusOutput | None = None
    transcript: list[AgentTurn] = []
    try:
        await bus.publish(thread_id, {"type": "review_started", "thread_id": thread_id})
        result = await orchestrator.run(
            ReviewContext.from_user_input(payload.content), on_event=publisher
        )
        consensus = result.output
        transcript = result.transcript
        reply_text = _render_reply(consensus)
        await bus.publish(
            thread_id,
            {
                "type": "review_completed",
                "thread_id": thread_id,
                "consensus": consensus.model_dump(),
            },
        )
    except Exception:
        logger.exception(
            "orchestrator failed for thread=%s",
            thread_id,
            extra={"request_id": request_id},
        )
        reply_text = _AGENT_FAILURE_REPLY
        await bus.publish(thread_id, {"type": "review_failed", "thread_id": thread_id})

    await append_chat_message(
        session,
        thread_id=thread_id,
        role="assistant",
        content=reply_text,
        consensus=consensus.model_dump() if consensus else None,
        transcript=[turn.model_dump() for turn in transcript] if transcript else None,
    )
    await session.commit()

    logger.info(
        "chat message thread=%s message=%s len=%d",
        thread_id,
        message_id,
        len(payload.content),
        extra={"request_id": request_id},
    )

    return ChatMessageResponse(
        thread_id=thread_id,
        message_id=message_id,
        reply=reply_text,
        consensus=consensus,
        transcript=transcript,
    )


@router.get("/threads", response_model=ThreadsResponse)
async def list_threads(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ThreadsResponse:
    rows = await list_thread_summaries(session)
    return ThreadsResponse(threads=[_render_thread_summary(row) for row in rows])


@router.get("/threads/{thread_id}", response_model=ChatThreadResponse)
async def get_thread(
    thread_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ChatThreadResponse:
    rows = await load_thread_messages(session, thread_id)
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="thread not found")
    return ChatThreadResponse(
        thread_id=thread_id,
        messages=[_render_message(row) for row in rows],
    )


@router.get("/threads/{thread_id}/events")
async def stream_thread_events(thread_id: str) -> StreamingResponse:
    """合議ターン / ライフサイクルイベントの SSE 配信。

    クライアント切断時は gen 内で `CancelledError` が飛ぶので、`finally` で
    必ず unsubscribe する。15 秒間 publish が無ければ `: keep-alive` を送る。
    """

    bus = get_event_bus()
    queue = bus.subscribe(thread_id)

    async def gen():
        try:
            yield _sse_format({"type": "stream_open", "thread_id": thread_id})
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=_SSE_KEEPALIVE_SECONDS)
                except TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                yield _sse_format(event)
        except asyncio.CancelledError:
            raise
        finally:
            bus.unsubscribe(thread_id, queue)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def _sse_format(event: dict[str, Any]) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def _render_reply(output: ConsensusOutput) -> str:
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


def _render_message(row: ChatMessage) -> dict[str, Any]:
    out: dict[str, Any] = {
        "message_id": row.message_id,
        "role": row.role,
        "content": row.content,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
    if row.consensus_json is not None:
        out["consensus"] = row.consensus_json
    if row.transcript_json is not None:
        out["transcript"] = row.transcript_json
    if row.action_payload is not None:
        out["action_payload"] = row.action_payload
    return out


def _render_thread_summary(row: ThreadSummary) -> ThreadSummaryModel:
    return ThreadSummaryModel(
        thread_id=row.thread_id,
        last_message_at=row.last_message_at.isoformat() if row.last_message_at else None,
        last_role=row.last_role,
        last_excerpt=row.last_excerpt,
        session_id=row.session_id,
        repository_name=row.repository_name,
        pr_number=row.pr_number,
        status=row.status,
        has_pending_action=row.has_pending_action,
    )
