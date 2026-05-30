import logging
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
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
from norn.db.repositories import append_chat_message, load_thread_messages

router = APIRouter(tags=["chat"])
logger = logging.getLogger("norn.api.routes.chat")


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

    consensus: ConsensusOutput | None = None
    transcript: list[AgentTurn] = []
    try:
        result = await orchestrator.run(ReviewContext.from_user_input(payload.content))
        consensus = result.output
        transcript = result.transcript
        reply_text = _render_reply(consensus)
    except Exception:
        logger.exception(
            "orchestrator failed for thread=%s",
            thread_id,
            extra={"request_id": request_id},
        )
        reply_text = _AGENT_FAILURE_REPLY

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
    return out
