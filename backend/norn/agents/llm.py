"""Azure OpenAI への Semantic Kernel ラッパー。

Semantic Kernel の AzureChatCompletion / OpenAIChatCompletion コネクタ経由。
Foundry の OpenAI v1 エンドポイントと従来の `.openai.azure.com` の両方に対応。
tenacity でリトライを掛け、オーケストレータからは LLMClient プロトコル経由で呼び出す。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from openai import APIConnectionError, APITimeoutError, AsyncOpenAI, RateLimitError
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion, OpenAIChatCompletion
from semantic_kernel.contents.chat_history import ChatHistory
from semantic_kernel.exceptions.service_exceptions import ServiceResponseException
from semantic_kernel.kernel import Kernel
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

if TYPE_CHECKING:
    from semantic_kernel.connectors.ai.chat_completion_client_base import ChatCompletionClientBase
    from semantic_kernel.connectors.ai.prompt_execution_settings import PromptExecutionSettings

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


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, _RETRYABLE):
        return True
    return isinstance(exc, ServiceResponseException) and isinstance(exc.__cause__, _RETRYABLE)


def _normalize_foundry_v1_endpoint(endpoint: str) -> str:
    base = endpoint.rstrip("/")
    if base.endswith("/openai/v1"):
        return base
    return f"{base}/openai/v1"


def _uses_foundry_v1_endpoint(endpoint: str) -> bool:
    return "services.ai.azure.com" in endpoint or endpoint.rstrip("/").endswith("/openai/v1")


def _build_connector(settings: Settings) -> ChatCompletionClientBase:
    deployment = settings.azure_openai_deployment
    if _uses_foundry_v1_endpoint(settings.azure_openai_endpoint):
        client = AsyncOpenAI(
            api_key=settings.azure_openai_api_key,
            base_url=_normalize_foundry_v1_endpoint(settings.azure_openai_endpoint),
        )
        connector = OpenAIChatCompletion(ai_model_id=deployment, async_client=client)
        logger.info(
            "Azure LLM client mode=foundry_v1 connector=OpenAIChatCompletion deployment=%s",
            deployment,
        )
        return connector

    connector = AzureChatCompletion(
        deployment_name=deployment,
        endpoint=settings.azure_openai_endpoint,
        api_key=settings.azure_openai_api_key,
        api_version=settings.azure_openai_api_version,
    )
    logger.info(
        "Azure LLM client mode=azure_classic connector=AzureChatCompletion deployment=%s",
        deployment,
    )
    return connector


def build_chat_kernel(settings: Settings) -> Kernel:
    """Semantic Kernel Agent Framework 用 Kernel（Azure OpenAI コネクタ付き）。"""
    kernel = Kernel()
    kernel.add_service(_build_connector(settings))
    return kernel


def _to_chat_history(messages: list[ChatMessage]) -> ChatHistory:
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
    return history


def _build_execution_settings(
    connector: ChatCompletionClientBase,
    *,
    response_format: type | None,
) -> PromptExecutionSettings:
    settings = connector.get_prompt_execution_settings_class()()
    if response_format is not None:
        settings.response_format = response_format
    return settings


class AzureLLMClient:
    """Azure OpenAI / AI Foundry 向け本番実装（Semantic Kernel コネクタ経由）。"""

    def __init__(self, settings: Settings) -> None:
        self._connector: ChatCompletionClientBase = _build_connector(settings)

    @retry(
        retry=retry_if_exception(_is_retryable),
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
        history = _to_chat_history(messages)
        settings = _build_execution_settings(
            self._connector,
            response_format=response_format,
        )
        results = await self._connector.get_chat_message_contents(history, settings)
        if not results:
            raise RuntimeError("Semantic Kernel connector returned no chat messages")
        content = results[0].content
        if not content:
            raise RuntimeError("Semantic Kernel connector returned empty content")
        return content
