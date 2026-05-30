"""Azure OpenAI への薄いラッパー。

Semantic Kernel の AzureChatCompletion を使い、tenacity でリトライを掛ける。
オーケストレータからは LLMClient プロトコル経由で呼び出すので、
テストではフェイクを差し込める。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from openai import APIConnectionError, APITimeoutError, RateLimitError
from semantic_kernel.connectors.ai.open_ai import (
    AzureChatCompletion,
    OpenAIChatPromptExecutionSettings,
)
from semantic_kernel.contents import ChatHistory
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

if TYPE_CHECKING:
    from norn.config import Settings

logger = logging.getLogger("norn.agents.llm")


@dataclass(frozen=True)
class ChatMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


class LLMClient(Protocol):
    """エージェントが LLM を叩くための最小プロトコル。"""

    async def complete(
        self,
        messages: list[ChatMessage],
        *,
        response_format: type | None = None,
    ) -> str: ...


_RETRYABLE = (APIConnectionError, APITimeoutError, RateLimitError)


class AzureLLMClient:
    """Semantic Kernel の AzureChatCompletion を使う本番実装。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._service = AzureChatCompletion(
            api_key=settings.azure_openai_api_key,
            endpoint=settings.azure_openai_endpoint,
            deployment_name=settings.azure_openai_deployment,
            api_version=settings.azure_openai_api_version,
        )

    @retry(
        retry=retry_if_exception_type(_RETRYABLE),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def complete(
        self,
        messages: list[ChatMessage],
        *,
        response_format: type | None = None,
    ) -> str:
        history = ChatHistory()
        for msg in messages:
            if msg.role == "system":
                history.add_system_message(msg.content)
            elif msg.role == "user":
                history.add_user_message(msg.content)
            elif msg.role == "assistant":
                history.add_assistant_message(msg.content)
            else:
                raise ValueError(f"unsupported role: {msg.role}")

        settings = OpenAIChatPromptExecutionSettings()
        if response_format is not None:
            settings.response_format = response_format

        results = await self._service.get_chat_message_contents(
            chat_history=history,
            settings=settings,
        )
        if not results:
            raise RuntimeError("Azure OpenAI returned no content")
        return str(results[0].content or "")
