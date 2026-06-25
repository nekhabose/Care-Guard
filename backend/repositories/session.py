import uuid

from sqlalchemy import delete, select

from models.db import ConversationTurn, OutreachSession
from .base import BaseRepository


class SessionRepository(BaseRepository[OutreachSession]):
    model = OutreachSession

    async def get_by_patient(self, patient_id: uuid.UUID) -> list[OutreachSession]:
        return await self.filter_by(patient_id=patient_id)

    async def get_pending(self) -> list[OutreachSession]:
        return await self.filter_by(status="scheduled")

    async def get_by_twilio_sid(self, call_sid: str) -> OutreachSession | None:
        return await self.first_by(twilio_call_sid=call_sid)


class TurnRepository(BaseRepository[ConversationTurn]):
    model = ConversationTurn

    async def get_by_session(self, session_id: uuid.UUID) -> list[ConversationTurn]:
        result = await self.db.execute(
            select(ConversationTurn)
            .where(ConversationTurn.session_id == session_id)
            .order_by(ConversationTurn.created_at)
        )
        return list(result.scalars().all())

    async def delete_by_sessions(self, session_ids: list[uuid.UUID]) -> int:
        """Hard-delete all turns for the given sessions (right to erasure)."""
        if not session_ids:
            return 0
        result = await self.db.execute(
            delete(ConversationTurn).where(ConversationTurn.session_id.in_(session_ids))
        )
        await self.db.flush()
        return result.rowcount or 0
