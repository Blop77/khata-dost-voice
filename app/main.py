"""Voice turn pipeline: audio -> transcript (Sarvam) -> understanding + reply (Claude) -> speech (Sarvam)."""
import json
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, File, Form, HTTPException, UploadFile  # noqa: E402
from fastapi.responses import StreamingResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from app import brain, speech  # noqa: E402
from app.tracks import load_tracks  # noqa: E402

WEB_DIR = Path(__file__).resolve().parent.parent / "web"

app = FastAPI(title="Voice-first starter")


@app.get("/api/config")
def config():
    tracks = load_tracks()
    return {
        "tracks": {k: {"title": t["title"], "greeting": t["greeting"]} for k, t in tracks.items()},
        "speech": speech.speech_enabled(),
        "llm": brain.provider() if brain.llm_enabled() else None,
    }


@app.post("/api/turn")
async def turn(
    track: str = Form(...),
    history: str = Form("[]"),
    text: str | None = Form(None),
    audio: UploadFile | None = File(None),
):
    tracks = load_tracks()
    if track not in tracks:
        raise HTTPException(404, f"unknown track {track!r}")
    cfg = tracks[track]

    language_code = None
    if audio is not None:
        try:
            stt = await speech.transcribe(await audio.read(), audio.filename or "audio.webm", audio.content_type or "audio/webm")
        except RuntimeError as e:
            raise HTTPException(400, str(e))
        text, language_code = stt["transcript"], stt["language_code"]
    if not text or not text.strip():
        raise HTTPException(400, "didn't catch that - try again")

    result = await brain.respond(cfg, json.loads(history), text, language_code)
    tts_lang = language_code if language_code in brain.LANGUAGE_NAMES else cfg.get("default_language", "en-IN")

    # Speech is fetched separately from /api/tts so the text shows up without waiting on audio.
    return {
        "transcript": text,
        "language_code": language_code,
        "reply": result["reply"],
        "fields": result["fields"],
        "done": result["done"],
        "tts_language": tts_lang,
    }


@app.get("/api/tts")
async def tts(text: str, lang: str = "en-IN"):
    if not speech.speech_enabled():
        raise HTTPException(503, "SARVAM_API_KEY not set")
    return StreamingResponse(speech.stream_speech(text, lang), media_type="audio/mpeg")


app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
