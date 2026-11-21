# Voice-first starter (India Runs on Voice hackathon)

Speak in any Indian language, mixed with English if you like. The app transcribes it, understands it, collects structured data, and replies out loud in the same language.

```
mic → Sarvam STT (auto language detect) → Claude (reply + structured fields) → Sarvam TTS → speaker
```

## Run

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # macOS/Linux: .venv/bin/python
cp .env.example .env   # add ANTHROPIC_API_KEY and SARVAM_API_KEY
.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000. If a key is missing, that stage runs in mock mode. Without Sarvam, type instead of talking and the browser reads replies aloud.

## Adapt it to a new problem (e.g. on 27 Nov)

Add a file to `tracks/`. The app picks it up without a restart.

```json
{
  "title": "…",
  "default_language": "hi-IN",
  "greeting": "First thing the app says",
  "persona": "Who the assistant is and what it's collecting",
  "fields": { "field_name": "what it means / format" }
}
```

Each turn returns every field collected so far, plus `done: true` once the user confirms. You can then save the result, send it to WhatsApp, or file it with an API.

## Files

- `app/main.py`: `/api/config` and `/api/turn` (audio or text in, reply + fields + audio out)
- `app/speech.py`: Sarvam speech-to-text (`saaras:v4`, `language_code=unknown`) and streaming text-to-speech over WebSocket (`bulbul:v3`, MP3). Audio starts in about 0.3 s; the REST endpoint took 4–17 s.
- `app/brain.py`: the LLM, chosen with `LLM_PROVIDER`. Either OpenAI (`OPENAI_MODEL`, default `gpt-4.1-mini` for speed) or Claude (`claude-opus-5-5` with server-side refusal fallbacks). Both use JSON-schema structured output, so every turn returns the same shape.
- `web/`: tap-to-talk UI with a typing fallback and a live fields panel

## Deploy

Any Python host works. On Render, for example: build command `pip install -r requirements.txt`, start command `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, and set the env vars. The mic needs HTTPS, which hosted URLs provide.
