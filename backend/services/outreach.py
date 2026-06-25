"""
OutreachService — manages the lifecycle of a single outreach call.

Builds the AgentContext, wires up all callbacks, starts the CareAgent,
and handles post-call cleanup regardless of success or failure.
"""
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from agent.care_agent import AgentContext, CareAgent
from models.db import Discharge, Patient
from repositories.escalation import EscalationRepository
from repositories.session import SessionRepository, TurnRepository
from services.notification import BaseNotifier

logger = logging.getLogger(__name__)


class OutreachService:
    def __init__(
        self,
        db: AsyncSession,
        notifier: BaseNotifier,
        send_to_call_fn: object,    # async callable(call_sid: str, text: str)
    ) -> None:
        self._session_repo = SessionRepository(db)
        self._turn_repo = TurnRepository(db)
        self._escalation_repo = EscalationRepository(db)
        self._notifier = notifier
        self._send_to_call = send_to_call_fn

    async def start_call(
        self,
        session_id: uuid.UUID,
        patient: Patient,
        discharge: Discharge,
        twilio_call_sid: str,
    ) -> CareAgent:
        """Mark session in_progress, wire callbacks, return a ready CareAgent."""
        session = await self._session_repo.get(session_id)
        await self._session_repo.update(
            session,
            status="in_progress",
            started_at=datetime.now(timezone.utc),
            twilio_call_sid=twilio_call_sid,
        )

        async def escalation_callback(
            session_id: uuid.UUID, patient_id: uuid.UUID,
            severity: str, reason: str, symptoms: list[str],
        ) -> None:
            escalation = await self._escalation_repo.create(
                session_id=session_id,
                patient_id=patient_id,
                severity=severity,
                reason=reason,
                symptoms_flagged=symptoms,
                notified_at=datetime.now(timezone.utc),
            )
            await self._notifier.send_escalation(
                session_id=session_id,
                patient_id=patient_id,
                severity=severity,
                reason=reason,
                symptoms=symptoms,
            )
            logger.warning(
                "Escalation created id=%s severity=%s patient_id=%s",
                escalation.id, severity, patient_id,
            )

        async def turn_callback(role: str, content: str) -> None:
            await self._turn_repo.create(
                session_id=session_id,
                role=role,
                content=content,
            )

        async def send_to_call_callback(text: str, last: bool = True) -> None:
            await self._send_to_call(twilio_call_sid, text, last)

        ctx = AgentContext(
            session_id=session_id,
            patient=patient,
            discharge=discharge,
            escalation_callback=escalation_callback,
            turn_callback=turn_callback,
            send_to_call_callback=send_to_call_callback,
        )
        return CareAgent(ctx)

    async def complete_call(self, session_id: uuid.UUID, status: str = "completed") -> None:
        session = await self._session_repo.get(session_id)
        await self._session_repo.update(
            session,
            status=status,
            completed_at=datetime.now(timezone.utc),
        )
        logger.info("Session completed session_id=%s status=%s", session_id, status)
