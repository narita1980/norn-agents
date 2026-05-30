import json

import pytest

from norn.agents.llm import ChatMessage, LLMClient
from norn.agents.orchestrator import NornOrchestrator
from norn.agents.personas import MODERATOR, SKULD, URD, VERDANDI
from norn.agents.schemas import ConsensusOutput, ReviewContext


class FakeLLMClient(LLMClient):
    """合議ロジックを検証するためのフェイク。

    deliberative ターンの応答と moderator の JSON 応答を順に返す。
    """

    def __init__(
        self,
        deliberative_replies: list[str],
        moderator_payload: dict,
    ) -> None:
        self._deliberative = list(deliberative_replies)
        self._moderator_payload = moderator_payload
        self.calls: list[dict] = []

    async def complete(
        self,
        messages: list[ChatMessage],
        *,
        response_format: type | None = None,
    ) -> str:
        self.calls.append(
            {
                "system": messages[0].content,
                "user": messages[1].content,
                "response_format": response_format,
            }
        )
        if response_format is not None:
            return json.dumps(self._moderator_payload)
        if not self._deliberative:
            raise AssertionError("no deliberative replies left")
        return self._deliberative.pop(0)


@pytest.fixture
def moderator_payload() -> dict:
    return {
        "summary": "良い変更ですね、お疲れさまでした。",
        "must_fix": ["NULL 入力時のチェックを追加してください"],
        "next_pr": ["関数を 30 行以下に分割しましょう"],
        "growth": "型ヒントとテスト思考が育っています。次は契約による設計を学ぶと飛躍します。",
        "tone": "encouraging",
    }


async def test_orchestrator_runs_personas_in_order(moderator_payload: dict) -> None:
    fake = FakeLLMClient(
        deliberative_replies=["urd-critique", "verdandi-tone", "skuld-growth"],
        moderator_payload=moderator_payload,
    )
    orchestrator = NornOrchestrator(fake)

    await orchestrator.run(ReviewContext.from_user_input("def add(a, b): return a+b"))

    persona_order = [URD, VERDANDI, SKULD, MODERATOR]
    assert len(fake.calls) == len(persona_order)
    for call, persona in zip(fake.calls, persona_order, strict=True):
        assert call["system"] == persona.system_prompt

    assert fake.calls[-1]["response_format"] is ConsensusOutput
    for call in fake.calls[:-1]:
        assert call["response_format"] is None


async def test_orchestrator_returns_structured_output(moderator_payload: dict) -> None:
    fake = FakeLLMClient(
        deliberative_replies=["urd", "verdandi", "skuld"],
        moderator_payload=moderator_payload,
    )
    orchestrator = NornOrchestrator(fake)

    result = await orchestrator.run(ReviewContext.from_user_input("input"))

    assert result.output.summary == moderator_payload["summary"]
    assert result.output.must_fix == moderator_payload["must_fix"]
    assert result.output.tone == "encouraging"
    assert len(result.transcript) == 4
    assert [turn.agent for turn in result.transcript] == [
        "urd",
        "verdandi",
        "skuld",
        "moderator",
    ]


async def test_orchestrator_passes_prior_turns_to_each_persona(moderator_payload: dict) -> None:
    fake = FakeLLMClient(
        deliberative_replies=["URD-SAYS", "VERDANDI-SAYS", "SKULD-SAYS"],
        moderator_payload=moderator_payload,
    )
    orchestrator = NornOrchestrator(fake)

    await orchestrator.run(ReviewContext.from_user_input("the input"))

    assert "前段の発言はありません" in fake.calls[0]["user"]
    assert "URD-SAYS" in fake.calls[1]["user"]
    assert "URD-SAYS" in fake.calls[2]["user"] and "VERDANDI-SAYS" in fake.calls[2]["user"]
    moderator_prompt = fake.calls[3]["user"]
    assert "URD-SAYS" in moderator_prompt
    assert "VERDANDI-SAYS" in moderator_prompt
    assert "SKULD-SAYS" in moderator_prompt


async def test_orchestrator_propagates_json_error(moderator_payload: dict) -> None:
    fake = FakeLLMClient(
        deliberative_replies=["a", "b", "c"],
        moderator_payload=moderator_payload,
    )

    async def broken_complete(messages, *, response_format=None):
        if response_format is not None:
            return "not json at all"
        return "ok"

    fake.complete = broken_complete  # type: ignore[assignment]
    orchestrator = NornOrchestrator(fake)

    with pytest.raises(json.JSONDecodeError):
        await orchestrator.run(ReviewContext.from_user_input("input"))


async def test_orchestrator_rejects_invalid_schema() -> None:
    bad_payload = {"summary": "ok"}  # missing required fields

    async def stub_complete(messages, *, response_format=None):
        if response_format is not None:
            return json.dumps(bad_payload)
        return "deliberative"

    class StubLLM:
        complete = staticmethod(stub_complete)

    orchestrator = NornOrchestrator(StubLLM())  # type: ignore[arg-type]

    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        await orchestrator.run(ReviewContext.from_user_input("input"))
