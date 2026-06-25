"""
CareAgent — orchestrates the post-discharge conversation.

Responsibilities:
- Builds the tool registry for this session.
- Selects the condition-specific protocol.
- Drives a provider-agnostic multi-turn LLM conversation.
- Persists every conversation turn.
- Hands transcribed patient speech in via inject_patient_input().

The agent is intentionally decoupled from Twilio, the DB, and the LLM
provider. All three are injected so the agent remains unit-testable
and supports any backend (Claude, DeepSeek, etc.) via build_llm_client().
"""
import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine

from config import get_settings
from models.db import Discharge, Patient

from .llm import (
    LLMClient,
    Message,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    build_llm_client,
)
from .protocols.factory import ProtocolFactory
from .tools.escalation import EscalationTool
from .tools.medication import MedicationTool
from .tools.registry import ToolRegistry
from .tools.scheduling import SchedulingTool
from .tools.symptom import SymptomTool

logger = logging.getLogger(__name__)
settings = get_settings()

EscalationCallback = Callable[..., Coroutine[Any, Any, None]]
TurnCallback = Callable[[str, str], Coroutine[Any, Any, None]]
# Signature: (text, last=True). last=False for streamed deltas mid-turn,
# last=True to mark the end of the agent's turn so ConversationRelay listens.
SendToCallCallback = Callable[..., Coroutine[Any, Any, None]]


@dataclass
class AgentContext:
    session_id: uuid.UUID
    patient: Patient
    discharge: Discharge
    escalation_callback: EscalationCallback
    turn_callback: TurnCallback
    send_to_call_callback: SendToCallCallback

    # Shared mutable state passed into tools
    recorded_symptoms: list[dict[str, Any]] = field(default_factory=list)
    adherence_log: list[dict[str, Any]] = field(default_factory=list)
    scheduling_log: list[dict[str, Any]] = field(default_factory=list)


class _OutgoingTurn:
    """Streams an agent turn to the call, one token behind.

    ConversationRelay treats the text frame with ``last=True`` as the end of the
    agent's turn and only then resumes listening. An empty trailing frame is not
    a reliable end signal, so we hold the most recent token back and emit it with
    ``last=True`` in ``finish()`` — i.e. the final *real* token carries the
    end-of-turn marker. All earlier tokens stream immediately with ``last=False``.
    """

    def __init__(self, send: SendToCallCallback) -> None:
        self._send = send
        self._pending: str | None = None

    async def feed(self, delta: str) -> None:
        if not delta:
            return
        if self._pending is not None:
            await self._send(self._pending, last=False)
        self._pending = delta

    async def finish(self) -> None:
        if self._pending is not None:
            await self._send(self._pending, last=True)
            self._pending = None
        else:
            # No text streamed this turn (e.g. tool-only) — still close the turn.
            await self._send("", last=True)


class CareAgent:
    def __init__(
        self,
        ctx: AgentContext,
        llm: LLMClient | None = None,
    ) -> None:
        self._ctx = ctx
        self._llm: LLMClient = llm or build_llm_client()
        self._registry = self._build_registry()
        self._protocol = ProtocolFactory.get(ctx.discharge.hrrp_condition)
        self._patient_input_queue: asyncio.Queue[str | None] = asyncio.Queue()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """Drive the full conversation until the agent says goodbye."""
        messages: list[Message] = []
        system_prompt = self._build_system_prompt()

        opening = self._build_opening()
        await self._emit_turn("agent", opening)
        await self._ctx.send_to_call_callback(opening, last=True)
        messages.append(Message(role="assistant", content=[TextBlock(text=opening)]))

        while True:
            patient_text = await self._wait_for_patient_input()
            if patient_text is None:
                break

            await self._emit_turn("patient", patient_text)
            messages.append(Message(role="user", content=[TextBlock(text=patient_text)]))

            # Stream this turn's speech; the streamer marks the FINAL token with
            # last=True (ConversationRelay's end-of-turn signal) so it returns to
            # listening. An empty trailing frame is NOT a reliable end signal.
            streamer = _OutgoingTurn(self._ctx.send_to_call_callback)
            try:
                messages = await self._agent_turn(messages, system_prompt, streamer)
                await streamer.finish()
            except Exception:
                # Any failure (LLM error, network, etc.) must not leave the caller
                # in silence. Speak a graceful fallback and end the call.
                logger.exception(
                    "Agent turn failed session_id=%s", self._ctx.session_id
                )
                await self._safe_say(
                    "I'm sorry, I'm having a little trouble on my end right now. "
                    "Someone from the care team will call you back shortly. Take care."
                )
                break

            last = self._last_agent_text(messages)
            if last and self._is_closing(last):
                break

    async def _safe_say(self, text: str) -> None:
        """Speak a single utterance, swallowing transport errors (best-effort)."""
        try:
            await self._emit_turn("agent", text)
            await self._ctx.send_to_call_callback(text, last=True)
        except Exception:
            logger.warning("Failed to deliver fallback message session_id=%s",
                           self._ctx.session_id)

    async def inject_patient_input(self, text: str) -> None:
        """Called by the WebSocket handler when patient speech arrives."""
        await self._patient_input_queue.put(text)

    async def end_call(self) -> None:
        """Signal the conversation loop to stop gracefully."""
        await self._patient_input_queue.put(None)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_registry(self) -> ToolRegistry:
        registry = ToolRegistry()
        ctx = self._ctx
        registry.register(SymptomTool(ctx.recorded_symptoms))
        registry.register(MedicationTool(ctx.adherence_log))
        registry.register(EscalationTool(
            session_id=ctx.session_id,
            patient_id=ctx.patient.id,
            escalation_callback=ctx.escalation_callback,
        ))
        registry.register(SchedulingTool(ctx.scheduling_log))
        return registry

    def _build_system_prompt(self) -> str:
        ctx = self._ctx
        meds = self._format_medications(ctx.discharge.medications or [])
        appts = self._format_appointments(ctx.discharge.followup_appointments or [])
        return self._protocol.build_system_prompt(
            hospital_name=ctx.discharge.hospital_name,
            patient_first_name=ctx.patient.first_name,
            patient_last_name=ctx.patient.last_name,
            date_of_birth=self._format_dob(ctx.patient.date_of_birth),
            discharge_date=str(ctx.discharge.discharge_date),
            diagnosis=ctx.discharge.primary_diagnosis_name or "recent illness",
            medications=meds,
            followup_appointments=appts,
            instructions_summary=ctx.discharge.instructions_summary or "Follow up as directed.",
        )

    def _build_opening(self) -> str:
        # Identity is unverified at this point, so disclose NO health information —
        # just ask for the patient by name. The system prompt drives date-of-birth
        # verification before anything about the discharge is mentioned.
        first = self._ctx.patient.first_name
        last = self._ctx.patient.last_name
        return f"Hello, may I please speak with {first} {last}?"

    @staticmethod
    def _format_dob(dob: Any) -> str:
        if not dob:
            return "unknown"
        try:
            return dob.strftime("%B %-d, %Y")  # e.g. "March 14, 1948"
        except (ValueError, AttributeError):
            return str(dob)

    async def _agent_turn(
        self, messages: list[Message], system_prompt: str, streamer: "_OutgoingTurn"
    ) -> list[Message]:
        """One agent turn — handles tool calls recursively until end_turn.

        Assistant text is streamed to ``streamer`` as it is generated; the
        streamer buffers one token so run() can flush the final token with
        last=True after the whole turn (incl. tool round-trips) resolves.
        """
        response = await self._llm.stream_message(
            system=system_prompt,
            messages=messages,
            tools=self._registry.definitions,
            max_tokens=settings.llm_max_tokens,
            on_text=streamer.feed,
        )

        if response.stop_reason == "tool_use":
            # Any text spoken before the tool call was already streamed; persist it.
            if response.text:
                await self._emit_turn("agent", response.text)
            messages.append(Message(role="assistant", content=list(response.content)))
            tool_results = await self._handle_tool_calls(response.tool_uses)
            messages.append(Message(role="user", content=tool_results))
            return await self._agent_turn(messages, system_prompt, streamer)

        if response.text:
            await self._emit_turn("agent", response.text)
            messages.append(Message(
                role="assistant",
                content=[TextBlock(text=response.text)],
            ))

        return messages

    async def _handle_tool_calls(
        self, tool_uses: list[ToolUseBlock]
    ) -> list[ToolResultBlock]:
        results: list[ToolResultBlock] = []
        for tool_use in tool_uses:
            result = await self._registry.execute(tool_use.name, **tool_use.input)
            results.append(ToolResultBlock(
                tool_use_id=tool_use.id,
                content=result,
            ))
        return results

    async def _wait_for_patient_input(self) -> str | None:
        return await self._patient_input_queue.get()

    async def _emit_turn(self, role: str, content: str) -> None:
        try:
            await self._ctx.turn_callback(role, content)
        except Exception:
            logger.exception("Failed to persist conversation turn role=%s", role)

    @staticmethod
    def _last_agent_text(messages: list[Message]) -> str | None:
        for msg in reversed(messages):
            if msg.role == "assistant":
                texts = [b.text for b in msg.content if isinstance(b, TextBlock)]
                if texts:
                    return " ".join(texts)
        return None

    @staticmethod
    def _is_closing(text: str) -> bool:
        """True only on an unambiguous sign-off.

        Must NOT match ordinary politeness like "thank you" — the agent says that
        mid-conversation, and matching it would end the call after one reply.
        Being conservative is safe: if no sign-off is detected, the call still
        ends when the caller hangs up (the WS "disconnect" frame).
        """
        t = text.lower()
        closing_phrases = (
            "goodbye", "good-bye", "good bye", "bye for now", "take care",
            "have a good day", "have a great day", "have a wonderful day",
            "have a good rest", "rest of your day", "stay well", "stay safe",
        )
        return any(phrase in t for phrase in closing_phrases)

    @staticmethod
    def _format_medications(medications: list[dict[str, Any]]) -> str:
        if not medications:
            return "No medications listed."
        return "; ".join(
            f"{m.get('name', 'Unknown')} {m.get('dose', '')} {m.get('frequency', '')}".strip()
            for m in medications
        )

    @staticmethod
    def _format_appointments(appointments: list[dict[str, Any]]) -> str:
        if not appointments:
            return "No follow-up appointments scheduled."
        return "; ".join(
            f"{a.get('specialty', 'Provider')} on {a.get('scheduled_date', 'TBD')}"
            for a in appointments
        )
