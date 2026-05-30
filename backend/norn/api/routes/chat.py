import logging
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

router = APIRouter(tags=["chat"])
logger = logging.getLogger("norn.api.routes.chat")

_THREADS: dict[str, list[dict[str, Any]]] = defaultdict(list)


class ChatMessageRequest(BaseModel):
    thread_id: str | None = Field(default=None)
    content: str = Field(min_length=1, max_length=10_000)


class ChatMessageResponse(BaseModel):
    thread_id: str
    message_id: str
    reply: str


class ChatThreadResponse(BaseModel):
    thread_id: str
    messages: list[dict[str, Any]]


_PHASE1_REPLY = "（Phase 2 で Semantic Kernel が応答します）"  # noqa: RUF001


@router.post("/messages", response_model=ChatMessageResponse, status_code=status.HTTP_201_CREATED)
async def post_message(payload: ChatMessageRequest, request: Request) -> ChatMessageResponse:
    request_id = getattr(request.state, "request_id", "-")
    thread_id = payload.thread_id or str(uuid4())
    message_id = str(uuid4())
    now = datetime.now(UTC).isoformat()

    _THREADS[thread_id].append(
        {
            "message_id": message_id,
            "role": "user",
            "content": payload.content,
            "created_at": now,
        }
    )
    reply_id = str(uuid4())
    _THREADS[thread_id].append(
        {
            "message_id": reply_id,
            "role": "assistant",
            "content": _PHASE1_REPLY,
            "created_at": now,
        }
    )

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
        reply=_PHASE1_REPLY,
    )


@router.get("/threads/{thread_id}", response_model=ChatThreadResponse)
async def get_thread(thread_id: str) -> ChatThreadResponse:
    if thread_id not in _THREADS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="thread not found")
    return ChatThreadResponse(thread_id=thread_id, messages=list(_THREADS[thread_id]))


def _reset_threads_for_tests() -> None:
    _THREADS.clear()
