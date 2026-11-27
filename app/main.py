"""Voice turn pipeline: audio -> transcript (Sarvam) -> understanding + reply (Claude) -> speech (Sarvam)."""
import json
import time
from collections import defaultdict, deque
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile  # noqa: E402
from fastapi.responses import StreamingResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from app import brain, khata, ledger, speech  # noqa: E402
from app.tracks import load_tracks  # noqa: E402

WEB_DIR = Path(__file__).resolve().parent.parent / "web"

app = FastAPI(title="Khata Dost")


@app.on_event("startup")
def _seed_if_empty():
    # A fresh install (e.g. `docker compose up`) opens on a small demo khata instead of an empty screen.
    if not ledger.customers_with_balance():
        ledger.reset_demo()


@app.get("/api/config")
def config():
    tracks = load_tracks()
    return {
        "tracks": {k: {"title": t["title"], "greeting": t["greeting"]} for k, t in tracks.items()},
        "speech": speech.speech_enabled(),
        "llm": brain.provider() if brain.llm_enabled() else None,
        "shop": khata.SHOP,
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


# --- Khata Dost ----------------------------------------------------------------------------

_hits: dict[tuple[str, str], deque] = defaultdict(deque)


def _limit(request: Request, bucket: str, per_minute: int) -> None:
    """Small in-memory rate limit so a public demo link can't run up the speech and AI bills."""
    ip = request.headers.get("cf-connecting-ip") or (request.client.host if request.client else "?")
    q, now = _hits[(ip, bucket)], time.monotonic()
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= per_minute:
        raise HTTPException(429, "थोड़ा रुकिए - too many requests, try again in a minute")
    q.append(now)


@app.post("/api/khata/turn")
async def khata_turn(
    request: Request,
    session: str = Form(...),
    text: str | None = Form(None),
    audio: UploadFile | None = File(None),
):
    """One spoken (or typed) turn of the ledger conversation."""
    _limit(request, "turn", 30)
    if text and len(text) > 500:
        raise HTTPException(413, "too long - say one entry at a time")
    language_code, t0 = None, time.perf_counter()
    if audio is not None:
        data = await audio.read()
        if len(data) < 1500:  # a tap with no speech
            return {**khata.session_reply(session, "not_heard"), "transcript": ""}
        try:
            stt = await speech.transcribe(data, audio.filename or "audio.webm", audio.content_type or "audio/webm")
        except RuntimeError as e:
            raise HTTPException(400, str(e))
        except Exception:
            raise HTTPException(502, "Speech service did not respond. Try again, or type the entry.")
        text, language_code = stt["transcript"], stt["language_code"]
    stt_ms = int((time.perf_counter() - t0) * 1000)
    result = await khata.handle(session, text or "", language_code)
    return {**result, "transcript": text or "", "language_code": language_code,
            "timing_ms": {"speech_to_text": stt_ms if audio else 0, "total": int((time.perf_counter() - t0) * 1000)}}


@app.get("/api/khata/ledger")
def khata_ledger():
    customers = ledger.customers_with_balance()
    return {
        "shop": khata.SHOP,
        "customers": customers,
        "total_due": sum(c["balance"] for c in customers if c["balance"] > 0),
        "recent": ledger.recent_entries(15),
        "reminders": khata.reminders(),
        "reminder_window_open": khata.reminder_window_open(),
    }


@app.get("/api/khata/customer/{customer_id}")
def khata_customer(customer_id: int):
    c = ledger.customer_detail(customer_id)
    if not c:
        raise HTTPException(404, "no such customer")
    return c


@app.post("/api/khata/customer/{customer_id}")
def khata_update_customer(customer_id: int, phone: str | None = Form(None), language: str | None = Form(None),
                          consent: bool | None = Form(None)):
    """Owner adds a phone number, the customer's language, or records the customer's yes/no to reminders."""
    fields = {k: v for k, v in {"phone": phone, "language": language, "reminder_consent": consent}.items() if v is not None}
    c = ledger.update_customer(customer_id, **fields)
    if not c:
        raise HTTPException(404, "no such customer")
    return c


@app.post("/api/khata/reset-demo")
def khata_reset_demo():
    ledger.reset_demo()
    khata.SESSIONS.clear()
    return {"ok": True}


@app.get("/api/tts")
async def tts(request: Request, text: str, lang: str = "en-IN"):
    if not speech.speech_enabled():
        raise HTTPException(503, "SARVAM_API_KEY not set")
    _limit(request, "tts", 40)
    if len(text) > 400:  # ledger replies and reminders are short; don't let a public link synthesize essays
        raise HTTPException(413, "text too long")
    return StreamingResponse(speech.stream_speech(text, lang), media_type="audio/mpeg")


app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
