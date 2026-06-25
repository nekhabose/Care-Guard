"""
LLMClient — abstract base for all LLM providers.

Add a new provider by:
  1. Subclassing LLMClient
  2. Implementing create_message() with provider-native API calls
  3. Registering the subclass in factory.py

CareAgent is the only consumer; it never imports a concrete client.
"""
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import Any

from .types import LLMResponse, Message

# Invoked with each text delta as it is generated, for low-latency TTS streaming.
TextDeltaCallback = Callable[[str], Awaitable[None]]


class LLMClient(ABC):
    @abstractmethod
    async def create_message(
        self,
        *,
        system: str,
        messages: list[Message],
        tools: list[dict[str, Any]],
        max_tokens: int,
    ) -> LLMResponse:
        """
        Run one turn of the conversation.

        Args:
            system: System prompt.
            messages: Full conversation history in unified format.
            tools: Tool definitions in unified format (BaseTool.to_claude_definition()).
            max_tokens: Generation cap.

        Returns:
            LLMResponse with content blocks and a stop_reason.
        """

    async def stream_message(
        self,
        *,
        system: str,
        messages: list[Message],
        tools: list[dict[str, Any]],
        max_tokens: int,
        on_text: TextDeltaCallback,
    ) -> LLMResponse:
        """
        Run one turn, streaming assistant text to ``on_text`` as it is produced.

        Returns the same fully-assembled LLMResponse as ``create_message`` (so
        the caller can still inspect tool_uses / stop_reason). Providers with
        native streaming override this; the default falls back to a single
        ``create_message`` and emits the whole text at once.
        """
        response = await self.create_message(
            system=system, messages=messages, tools=tools, max_tokens=max_tokens
        )
        if response.text:
            await on_text(response.text)
        return response
