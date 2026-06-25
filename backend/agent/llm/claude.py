"""
ClaudeClient — Anthropic Claude provider implementation.
"""
from typing import Any

import anthropic

from .base import LLMClient, TextDeltaCallback
from .types import (
    LLMResponse,
    Message,
    StopReason,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
)


class ClaudeClient(LLMClient):
    def __init__(self, api_key: str, model: str) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model

    async def create_message(
        self,
        *,
        system: str,
        messages: list[Message],
        tools: list[dict[str, Any]],
        max_tokens: int,
    ) -> LLMResponse:
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system,
            tools=tools,
            messages=[self._to_native(m) for m in messages],
        )
        return self._from_native(response)

    async def stream_message(
        self,
        *,
        system: str,
        messages: list[Message],
        tools: list[dict[str, Any]],
        max_tokens: int,
        on_text: TextDeltaCallback,
    ) -> LLMResponse:
        """Stream text deltas to ``on_text`` while the model generates, then
        return the fully-assembled response (including any tool_use blocks)."""
        async with self._client.messages.stream(
            model=self._model,
            max_tokens=max_tokens,
            system=system,
            tools=tools,
            messages=[self._to_native(m) for m in messages],
        ) as stream:
            async for delta in stream.text_stream:
                if delta:
                    await on_text(delta)
            final = await stream.get_final_message()
        return self._from_native(final)

    # ------------------------------------------------------------------
    # Unified → Claude
    # ------------------------------------------------------------------

    @staticmethod
    def _to_native(msg: Message) -> dict[str, Any]:
        return {
            "role": msg.role,
            "content": [ClaudeClient._block_to_native(b) for b in msg.content],
        }

    @staticmethod
    def _block_to_native(block: Any) -> dict[str, Any]:
        if isinstance(block, TextBlock):
            return {"type": "text", "text": block.text}
        if isinstance(block, ToolUseBlock):
            return {"type": "tool_use", "id": block.id,
                    "name": block.name, "input": block.input}
        if isinstance(block, ToolResultBlock):
            return {"type": "tool_result", "tool_use_id": block.tool_use_id,
                    "content": block.content}
        raise TypeError(f"Unknown content block type: {type(block)}")

    # ------------------------------------------------------------------
    # Claude → Unified
    # ------------------------------------------------------------------

    @staticmethod
    def _from_native(response: Any) -> LLMResponse:
        blocks = []
        for block in response.content:
            if block.type == "text":
                blocks.append(TextBlock(text=block.text))
            elif block.type == "tool_use":
                blocks.append(ToolUseBlock(
                    id=block.id, name=block.name, input=block.input
                ))
        stop: StopReason = response.stop_reason or "end_turn"
        return LLMResponse(content=blocks, stop_reason=stop)
