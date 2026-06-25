"""
Twilio voice routes — TwiML response + WebSocket conversation handler.
"""
import asyncio
import logging
import uuid

from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from twilio.twiml.voice_response import Connect, VoiceResponse

from api.deps import get_db, get_notifier_dep, verify_twilio_signature
from config import get_settings
from repositories.discharge import DischargeRepository
from repositories.patient import PatientRepository
from repositories.session import SessionRepository
from security.auth import InvalidTokenError, create_stream_token, verify_stream_token
from services.notification import BaseNotifier
from services.outreach import OutreachService
from services.recording import get_recording_store

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/twilio", tags=["twilio"])


@router.post("/twiml", dependencies=[Depends(verify_twilio_signature)])
async def twiml_response(session_id: str):
    """Return TwiML that connects the call to our ConversationRelay WebSocket."""
    response = VoiceResponse()
    connect = Connect()
    # Bind the WebSocket to this session with a short-lived signed token so the
    # socket can't be opened by anyone who merely guesses the session UUID.
    stream_token = create_stream_token(session_id)
    connect.conversation_relay(
        url=f"wss://{settings.domain}/twilio/ws/{session_id}?token={stream_token}",
        welcome_greeting="Please hold for just a moment.",
        language="en-US",
        voice="en-US-Journey-F",
        transcription_provider="google",
    )
    response.append(connect)
    return Response(content=str(response), media_type="application/xml")


@router.post("/status", dependencies=[Depends(verify_twilio_signature)])
async def call_status_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Twilio status callback — update session status when call ends.

    Twilio posts status callbacks as application/x-www-form-urlencoded, so we
    read the form body rather than expecting a JSON object.
    """
    form = await request.form()
    call_sid = form.get("CallSid")
    call_status = form.get("CallStatus")
    if not call_sid:
        return {"ok": True}

    session_repo = SessionRepository(db)
    session = await session_repo.get_by_twilio_sid(call_sid)
    if session:
        status_map = {
            "completed": "completed",
            "no-answer": "no_answer",
            "busy": "no_answer",
            "failed": "failed",
        }
        mapped = status_map.get(call_status, "completed")
        await session_repo.update(session, status=mapped)

    return {"ok": True}


@router.post("/recording", dependencies=[Depends(verify_twilio_signature)])
async def recording_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Twilio recording-status callback — persist the recording to KMS-encrypted S3.

    Twilio stores the raw recording on its own (BAA-covered) infrastructure; we
    copy completed recordings into our encrypted bucket and keep only the S3 key
    on the session. No-op unless RECORDINGS_ENABLED.
    """
    form = await request.form()
    call_sid = form.get("CallSid")
    recording_url = form.get("RecordingUrl")
    recording_status = form.get("RecordingStatus")
    if not (call_sid and recording_url) or recording_status != "completed":
        return {"ok": True}

    session_repo = SessionRepository(db)
    session = await session_repo.get_by_twilio_sid(call_sid)
    if not session:
        return {"ok": True}

    store = get_recording_store()
    s3_key = await store.store_recording(session_id=session.id, recording_url=recording_url)
    if s3_key:
        await session_repo.update(session, recording_s3_key=s3_key)
    return {"ok": True}


def _authorize_stream(websocket: WebSocket, session_id: str) -> bool:
    """Validate the WS handshake token. In dev (signature validation off) a
    missing token is tolerated; in production a valid token is required."""
    token = websocket.query_params.get("token")
    if token:
        try:
            verify_stream_token(token, session_id)
            return True
        except InvalidTokenError:
            return False
    return not settings.twilio_validate_signatures


@router.websocket("/ws/{session_id}")
async def conversation_websocket(
    websocket: WebSocket,
    session_id: str,
    db: AsyncSession = Depends(get_db),
    notifier: BaseNotifier = Depends(get_notifier_dep),
):
    """
    WebSocket endpoint for Twilio ConversationRelay.

    Receives transcribed patient speech, feeds it to CareAgent,
    sends agent responses back to Twilio for TTS playback.
    """
    await websocket.accept()

    # Verify the handshake token minted by twiml_response before doing anything.
    if not _authorize_stream(websocket, session_id):
        logger.warning("Rejected unauthorized WS handshake session_id=%s", session_id)
        await websocket.close(code=1008)
        return

    session_uuid = uuid.UUID(session_id)

    # Load session context from DB
    session_repo = SessionRepository(db)
    patient_repo = PatientRepository(db)
    discharge_repo = DischargeRepository(db)

    session = await session_repo.get(session_uuid)
    if not session:
        await websocket.close(code=1008)
        return

    patient = await patient_repo.get(session.patient_id)
    discharge = await discharge_repo.get(session.discharge_id)

    async def send_to_call(call_sid: str, text: str, last: bool = True) -> None:
        """Send agent text to Twilio for TTS playback.

        Matches OutreachService's send_to_call_fn contract (call_sid, text, last);
        call_sid is unused here because ConversationRelay routes by socket.
        The agent streams partial tokens with last=False and sends last=True to
        end its turn, at which point ConversationRelay starts listening again.
        """
        try:
            await websocket.send_json({"type": "text", "token": text, "last": last})
        except Exception:
            logger.warning("Failed to send to call session_id=%s", session_id)

    outreach_service = OutreachService(db=db, notifier=notifier, send_to_call_fn=send_to_call)

    # ConversationRelay's first message is a "setup" frame with callSid at the
    # top level (older Media Streams used a nested "start" object).
    initial_data = await websocket.receive_json()
    call_sid = initial_data.get("callSid") or initial_data.get("start", {}).get("callSid", "")

    agent = await outreach_service.start_call(
        session_id=session_uuid,
        patient=patient,
        discharge=discharge,
        twilio_call_sid=call_sid,
    )

    agent_task = asyncio.create_task(agent.run())

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "prompt":
                patient_text = data.get("voicePrompt", "").strip()
                if patient_text:
                    await agent.inject_patient_input(patient_text)

            elif msg_type == "interrupt":
                # Caller spoke over the agent. ConversationRelay has already
                # stopped TTS playback on its side; their words arrive as a
                # following "prompt" frame, handled above.
                logger.info("Caller interrupted agent session_id=%s", session_id)

            elif msg_type == "disconnect":
                await agent.end_call()
                break

            else:
                # setup is consumed before this loop; log anything else (info,
                # dtmf, error) so we can see exactly what ConversationRelay sends.
                logger.info(
                    "Unhandled ConversationRelay message type=%s session_id=%s",
                    msg_type, session_id,
                )

    except WebSocketDisconnect:
        await agent.end_call()
    finally:
        agent_task.cancel()
        try:
            await agent_task
        except asyncio.CancelledError:
            pass
        await outreach_service.complete_call(session_uuid)
