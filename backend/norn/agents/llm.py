"""Azure OpenAI への薄いラッパー。

Foundry の OpenAI v1 エンドポイントと従来の `.openai.azure.com` の両方に対応。
tenacity でリトライを掛け、オーケストレータからは LLMClient プロトコル経由で呼び出す。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from openai import (
    APIConnectionError,
    APITimeoutError,
    AsyncAzureOpenAI,
    AsyncOpenAI,
    RateLimitError,
)
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


def _normalize_foundry_v1_endpoint(endpoint: str) -> str:
    base = endpoint.rstrip("/")
    if base.endswith("/openai/v1"):
        return base
    return f"{base}/openai/v1"


def _uses_foundry_v1_endpoint(endpoint: str) -> bool:
    return "services.ai.azure.com" in endpoint or endpoint.rstrip("/").endswith("/openai/v1")


def _to_openai_messages(messages: list[ChatMessage]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for msg in messages:
        if msg.role not in {"system", "user", "assistant"}:
            raise ValueError(f"unsupported role: {msg.role}")
        out.append({"role": msg.role, "content": msg.content})
    return out


class AzureLLMClient:
    """Azure OpenAI / AI Foundry 向け本番実装。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._model = settings.azure_openai_deployment
        if _uses_foundry_v1_endpoint(settings.azure_openai_endpoint):
            self._client: AsyncOpenAI | AsyncAzureOpenAI = AsyncOpenAI(
                api_key=settings.azure_openai_api_key,
                base_url=_normalize_foundry_v1_endpoint(settings.azure_openai_endpoint),
            )
            logger.info("Azure LLM client mode=foundry_v1 deployment=%s", self._model)
            return

        self._client = AsyncAzureOpenAI(
            api_key=settings.azure_openai_api_key,
            azure_endpoint=settings.azure_openai_endpoint,
            api_version=settings.azure_openai_api_version,
        )
        logger.info("Azure LLM client mode=azure_classic deployment=%s", self._model)

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
        openai_messages = _to_openai_messages(messages)
        if response_format is not None:
            return await self._complete_structured(openai_messages, response_format)
        return await self._complete_plain(openai_messages)

    async def _complete_plain(self, messages: list[dict[str, str]]) -> str:
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
        )
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("Azure OpenAI returned no content")
        return content

    async def _complete_structured(
        self,
        messages: list[dict[str, str]],
        response_format: type[Any],
    ) -> str:
        response = await self._client.beta.chat.completions.parse(
            model=self._model,
            messages=messages,
            response_format=response_format,
        )
        parsed = response.choices[0].message.parsed
        if parsed is not None:
            if hasattr(parsed, "model_dump_json"):
                return parsed.model_dump_json()
            return str(parsed)
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("Azure OpenAI returned no structured content")
        return content
