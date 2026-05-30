"""thread_id 単位の in-memory pub-sub。

`/chat/threads/{thread_id}/events` の SSE 配信に使う。シングルプロセス
（uvicorn `--workers 1`）専用。マルチワーカー運用に切り替えるときは
Redis Pub/Sub などに差し替える前提。
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger("norn.events.bus")

# サブスクライバが取りこぼした場合の保護策。これ以上溜まったら drop する。
_QUEUE_MAXSIZE = 64


class EventBus:
    """thread_id をキーにイベントをサブスクライブ／配信する。"""

    def __init__(self) -> None:
        self._subs: dict[str, set[asyncio.Queue[dict[str, Any]]]] = {}

    def subscribe(self, thread_id: str) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)
        self._subs.setdefault(thread_id, set()).add(queue)
        return queue

    def unsubscribe(self, thread_id: str, queue: asyncio.Queue[dict[str, Any]]) -> None:
        subs = self._subs.get(thread_id)
        if not subs:
            return
        subs.discard(queue)
        if not subs:
            self._subs.pop(thread_id, None)

    async def publish(self, thread_id: str, event: dict[str, Any]) -> None:
        for queue in list(self._subs.get(thread_id, set())):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning(
                    "event bus subscriber dropped: thread=%s queue_full", thread_id
                )
                self.unsubscribe(thread_id, queue)


_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    global _bus
    if _bus is None:
        _bus = EventBus()
    return _bus
