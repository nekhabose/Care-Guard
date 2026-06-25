"""Tests for the LLMClient streaming contract."""
import pytest

from agent.llm.base import LLMClient
from agent.llm.types import LLMResponse, Message, TextBlock, ToolUseBlock


class _FakeClient(LLMClient):
    """Non-streaming client — exercises the base-class stream fallback."""

    def __init__(self, response: LLMResponse) -> None:
        self._response = response
        self.create_calls = 0

    async def create_message(self, *, system, messages, tools, max_tokens) -> LLMResponse:
        self.create_calls += 1
        return self._response


@pytest.mark.asyncio
async def test_stream_fallback_emits_whole_text_once():
    client = _FakeClient(
        LLMResponse(content=[TextBlock(text="Hello there.")], stop_reason="end_turn")
    )
    chunks: list[str] = []

    async def on_text(delta: str) -> None:
        chunks.append(delta)

    resp = await client.stream_message(
        system="s", messages=[Message(role="user", content=[TextBlock(text="hi")])],
        tools=[], max_tokens=50, on_text=on_text,
    )

    assert client.create_calls == 1
    assert chunks == ["Hello there."]
    assert resp.stop_reason == "end_turn"


@pytest.mark.asyncio
async def test_stream_fallback_no_text_no_emit():
    # A tool-only response should not push any text to the call.
    client = _FakeClient(
        LLMResponse(
            content=[ToolUseBlock(id="t1", name="escalate_to_care_team", input={})],
            stop_reason="tool_use",
        )
    )
    chunks: list[str] = []

    async def on_text(delta: str) -> None:
        chunks.append(delta)

    resp = await client.stream_message(
        system="s", messages=[], tools=[], max_tokens=50, on_text=on_text
    )

    assert chunks == []
    assert resp.tool_uses and resp.tool_uses[0].name == "escalate_to_care_team"
