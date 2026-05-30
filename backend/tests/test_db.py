"""DB レイヤ単体テスト。FastAPI を介さず、独自の AsyncSession を立てる。"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

if TYPE_CHECKING:
    from pathlib import Path

from norn.agents.schemas import AgentTurn
from norn.db.models import Base
from norn.db.repositories import (
    append_agent_turns,
    append_chat_message,
    find_session_by_pr,
    get_or_create_review_session,
    load_prior_turns,
    load_thread_messages,
    mark_session_status,
)


@pytest.fixture
async def db_session(tmp_path: Path):
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'db_unit.db'}",
        future=True,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as session:
        yield session
    await engine.dispose()


async def test_get_or_create_review_session_is_idempotent(db_session) -> None:
    a = await get_or_create_review_session(db_session, repository_name="o/r", pr_number=10)
    await db_session.commit()

    b = await get_or_create_review_session(db_session, repository_name="o/r", pr_number=10)
    assert a.id == b.id
    assert a.chat_thread_id == b.chat_thread_id


async def test_get_or_create_assigns_chat_thread_id_when_absent(db_session) -> None:
    sess = await get_or_create_review_session(db_session, repository_name="o/r", pr_number=11)
    assert sess.chat_thread_id  # non-empty UUID
    assert sess.status == "running"


async def test_find_session_by_pr_returns_none_when_missing(db_session) -> None:
    result = await find_session_by_pr(db_session, repository_name="ghost/repo", pr_number=999)
    assert result is None


async def test_append_and_load_agent_turns_preserves_order(db_session) -> None:
    sess = await get_or_create_review_session(db_session, repository_name="o/r", pr_number=12)
    await append_agent_turns(
        db_session,
        sess.id,
        [
            AgentTurn(agent="urd", role_label="Urd（技術）", content="一つ目"),
            AgentTurn(agent="verdandi", role_label="Verdandi（共感・現在）", content="二つ目"),
            AgentTurn(agent="skuld", role_label="Skuld（未来・成長）", content="三つ目"),
        ],
    )
    await db_session.commit()

    turns = await load_prior_turns(db_session, sess.id)
    assert [t.agent for t in turns] == ["urd", "verdandi", "skuld"]
    assert turns[0].content == "一つ目"
    assert turns[2].content == "三つ目"


async def test_mark_session_status_updates_row(db_session) -> None:
    sess = await get_or_create_review_session(db_session, repository_name="o/r", pr_number=13)
    await db_session.commit()

    await mark_session_status(db_session, sess.id, "completed")
    await db_session.commit()

    again = await find_session_by_pr(db_session, repository_name="o/r", pr_number=13)
    assert again is not None
    assert again.status == "completed"


async def test_append_and_load_chat_messages_preserves_order(db_session) -> None:
    await append_chat_message(db_session, thread_id="t-1", role="user", content="hi")
    await append_chat_message(
        db_session,
        thread_id="t-1",
        role="assistant",
        content="hello",
        consensus={"summary": "ok"},
        transcript=[{"agent": "urd"}],
    )
    await db_session.commit()

    msgs = await load_thread_messages(db_session, "t-1")
    assert [m.role for m in msgs] == ["user", "assistant"]
    assert msgs[1].consensus_json == {"summary": "ok"}
    assert msgs[1].transcript_json == [{"agent": "urd"}]


async def test_load_thread_messages_returns_empty_for_unknown_thread(db_session) -> None:
    msgs = await load_thread_messages(db_session, "no-such-thread")
    assert msgs == []
