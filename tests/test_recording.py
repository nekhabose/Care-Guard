"""Call-recording storage — disabled by default; KMS-encrypted when enabled."""
import uuid
from unittest.mock import MagicMock

import pytest

import services.recording as R
from services.recording import NoOpRecordingStore, S3RecordingStore, get_recording_store


def test_disabled_returns_noop(monkeypatch):
    monkeypatch.setattr(R.settings, "recordings_enabled", False)
    assert isinstance(get_recording_store(), NoOpRecordingStore)


@pytest.mark.asyncio
async def test_noop_store_returns_none():
    key = await NoOpRecordingStore().store_recording(uuid.uuid4(), "https://x/REabc")
    assert key is None


@pytest.mark.asyncio
async def test_s3_store_uploads_with_kms(monkeypatch):
    monkeypatch.setattr(R.settings, "recordings_s3_bucket", "careguard-recordings")
    monkeypatch.setattr(R.settings, "kms_key_id", "kms-key-1")
    monkeypatch.setattr(R.settings, "twilio_account_sid", "ACtest")
    monkeypatch.setattr(R.settings, "twilio_auth_token", "tok")

    # Fake the Twilio media download.
    class _Resp:
        content = b"audio-bytes"

        def raise_for_status(self):  # noqa: D401
            return None

    class _Http:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, auth=None):
            assert url.endswith(".mp3")
            return _Resp()

    monkeypatch.setattr(R.httpx, "AsyncClient", lambda *a, **k: _Http())

    store = S3RecordingStore.__new__(S3RecordingStore)  # skip boto3 client build
    store._s3 = MagicMock()
    store._bucket = "careguard-recordings"
    store._kms_key_id = "kms-key-1"

    sid = uuid.uuid4()
    key = await store.store_recording(sid, "https://api.twilio.com/REabc")

    assert key == f"recordings/{sid}.mp3"
    _, kwargs = store._s3.put_object.call_args
    assert kwargs["ServerSideEncryption"] == "aws:kms"
    assert kwargs["SSEKMSKeyId"] == "kms-key-1"
    assert kwargs["Bucket"] == "careguard-recordings"
