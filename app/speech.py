"""Speech in / speech out via Sarvam AI. Falls back to mock mode when SARVAM_API_KEY is unset."""
import base64
import json
import os
from collections.abc import AsyncIterator

import httpx
from websockets.asyncio.client import connect

SARVAM_BASE = "https://api.sarvam.ai"
# bulbul TTS rejects longer inputs (2500 chars on v3); keep replies well under this.
TTS_MAX_CHARS = 1500
DEFAULT_SPEAKER = "shubh"  # bulbul:v3 default voice; the streaming API requires one


def _key() -> str | None:
    return os.getenv("SARVAM_API_KEY") or None


def speech_enabled() -> bool:
    return _key() is not None


async def transcribe(audio: bytes, filename: str, content_type: str) -> dict:
    """Returns {"transcript": str, "language_code": str | None}. Auto-detects the language."""
    if not _key():
        raise RuntimeError("SARVAM_API_KEY not set - type your message instead, or add a key to .env")
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{SARVAM_BASE}/speech-to-text",
            headers={"api-subscription-key": _key()},
            files={"file": (filename, audio, content_type)},
            data={
                "model": os.getenv("SARVAM_STT_MODEL", "saaras:v4"),
                "language_code": "unknown",
            },
        )
    r.raise_for_status()
    body = r.json()
    return {"transcript": body.get("transcript", ""), "language_code": body.get("language_code")}


async def stream_speech(text: str, language_code: str) -> AsyncIterator[bytes]:
    """Yields MP3 chunks as Sarvam generates them (first chunk in ~0.3s vs 4-17s for the REST endpoint)."""
    model = os.getenv("SARVAM_TTS_MODEL", "bulbul:v3")
    url = f"wss://api.sarvam.ai/text-to-speech/ws?model={model}&send_completion_event=true"
    async with connect(url, additional_headers={"Api-Subscription-Key": _key()}) as ws:
        await ws.send(json.dumps({"type": "config", "data": {
            "language_code": language_code,
            "speaker": os.getenv("SARVAM_TTS_SPEAKER") or DEFAULT_SPEAKER,
            "output_audio_codec": "mp3",
        }}))
        await ws.send(json.dumps({"type": "text", "data": {"text": text[:TTS_MAX_CHARS]}}))
        await ws.send(json.dumps({"type": "flush"}))
        async for raw in ws:
            msg = json.loads(raw)
            if msg["type"] == "audio":
                yield base64.b64decode(msg["data"]["audio"])
            elif msg["type"] == "event" and msg["data"].get("event_type") == "final":
                return
            elif msg["type"] == "error":
                raise RuntimeError(f"Sarvam TTS: {msg['data'].get('message')}")
