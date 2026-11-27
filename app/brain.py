"""Understanding + reply via an LLM (LLM_PROVIDER=claude | openai). Falls back to a mock when no key is set."""
import json
import os

import anthropic
import openai

LANGUAGE_NAMES = {
    "hi-IN": "Hindi", "bn-IN": "Bengali", "kn-IN": "Kannada", "ml-IN": "Malayalam",
    "mr-IN": "Marathi", "od-IN": "Odia", "pa-IN": "Punjabi", "ta-IN": "Tamil",
    "te-IN": "Telugu", "en-IN": "English", "gu-IN": "Gujarati", "as-IN": "Assamese",
    "ur-IN": "Urdu",
}

_client: anthropic.AsyncAnthropic | None = None
_openai_client: openai.AsyncOpenAI | None = None


def provider() -> str:
    return os.getenv("LLM_PROVIDER", "claude").lower()


def llm_enabled() -> bool:
    if provider() == "openai":
        return bool(os.getenv("OPENAI_API_KEY"))
    return bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN"))


def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic()
    return _client


def _get_openai() -> openai.AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = openai.AsyncOpenAI()
    return _openai_client


def _schema(track: dict) -> dict:
    # Every field is required-but-nullable so structured outputs can enforce the shape.
    fields = {
        name: {"type": ["string", "null"], "description": desc}
        for name, desc in track["fields"].items()
    }
    return {
        "type": "object",
        "properties": {
            "reply": {"type": "string", "description": "What to say back to the user, spoken aloud."},
            "fields": {
                "type": "object",
                "properties": fields,
                "required": list(fields),
                "additionalProperties": False,
            },
            "done": {"type": "boolean", "description": "True once every required field is collected and confirmed."},
        },
        "required": ["reply", "fields", "done"],
        "additionalProperties": False,
    }


def _system(track: dict) -> str:
    return f"""{track["persona"]}

You are talking to the user by VOICE. Your reply is converted to speech, so:
- Reply in the same language and script the user spoke in. If they mix languages (e.g. Kannada + English), mix the same way.
- Keep replies to one or two short sentences. Ask for one missing thing at a time.
- No markdown, lists, emojis or URLs.
- Transcripts may contain recognition errors and fillers; infer intent generously.

Collect these fields across the conversation. Return ALL fields collected so far on every turn (carry earlier values forward), using null for unknowns:
{json.dumps(track["fields"], indent=2, ensure_ascii=False)}

When every field is filled, read a short summary back and ask the user to confirm. Set done=true only after they confirm."""


async def respond(track: dict, history: list[dict], user_text: str, language_code: str | None) -> dict:
    """history: [{"role": "user"|"assistant", "text": str}, ...] from earlier turns."""
    if not llm_enabled():
        return {
            "reply": f"(mock) I heard: {user_text}. Add an LLM API key to .env for real replies.",
            "fields": {name: None for name in track["fields"]},
            "done": False,
        }

    lang = LANGUAGE_NAMES.get(language_code or "", None)
    content = user_text if not lang else f"[detected language: {lang}]\n{user_text}"
    messages = [{"role": m["role"], "content": m["text"]} for m in history]
    if messages and messages[0]["role"] == "assistant":
        # The UI opens with a spoken greeting; the API requires the first turn to be the user's.
        messages.insert(0, {"role": "user", "content": "(user opened the app)"})
    messages.append({"role": "user", "content": content})

    if provider() == "openai":
        return await _respond_openai(track, messages)

    # Refusal fallbacks are enabled: on a policy decline the API re-runs the request on a fallback model.
    response = await _get_client().beta.messages.create(
        model=os.getenv("CLAUDE_MODEL", "claude-opus-5-5"),
        max_tokens=4000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        system=[{"type": "text", "text": _system(track), "cache_control": {"type": "ephemeral"}}],
        output_config={
            # low effort keeps voice turns snappy; raise it if extraction quality suffers
            "effort": os.getenv("CLAUDE_EFFORT", "low"),
            "format": {"type": "json_schema", "schema": _schema(track)},
        },
        messages=messages,
    )
    if response.stop_reason == "refusal":
        return {"reply": "Sorry, I can't help with that.", "fields": {n: None for n in track["fields"]}, "done": False}

    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)


async def extract(system: str, messages: list[dict], schema: dict, name: str = "extract") -> dict | None:
    """One structured-output call with any system prompt and schema. Returns None if no key or on refusal."""
    if not llm_enabled():
        return None
    if provider() == "openai":
        kwargs = {}
        if effort := os.getenv("OPENAI_REASONING_EFFORT"):
            kwargs["reasoning_effort"] = effort  # reasoning models reject temperature
        else:
            kwargs["temperature"] = 0  # same words in, same entry out
        response = await _get_openai().chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            messages=[{"role": "system", "content": system}, *messages],
            response_format={"type": "json_schema", "json_schema": {"name": name, "schema": schema, "strict": True}},
            **kwargs,
        )
        message = response.choices[0].message
        return None if message.refusal else json.loads(message.content)
    response = await _get_client().beta.messages.create(
        model=os.getenv("CLAUDE_MODEL", "claude-opus-5-5"),
        max_tokens=2000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        output_config={"effort": os.getenv("CLAUDE_EFFORT", "low"), "format": {"type": "json_schema", "schema": schema}},
        messages=messages,
    )
    if response.stop_reason == "refusal":
        return None
    return json.loads(next(b.text for b in response.content if b.type == "text"))


async def _respond_openai(track: dict, messages: list[dict]) -> dict:
    kwargs = {}
    # Only reasoning models accept reasoning_effort; leave OPENAI_REASONING_EFFORT blank for others.
    if effort := os.getenv("OPENAI_REASONING_EFFORT"):
        kwargs["reasoning_effort"] = effort
    response = await _get_openai().chat.completions.create(
        # gpt-4.1-mini: ~1.5s/turn; gpt-5-mini at medium effort measured 7-8s, too slow for voice
        model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        messages=[{"role": "system", "content": _system(track)}, *messages],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "voice_turn", "schema": _schema(track), "strict": True},
        },
        **kwargs,
    )
    message = response.choices[0].message
    if message.refusal:
        return {"reply": "Sorry, I can't help with that.", "fields": {n: None for n in track["fields"]}, "done": False}
    return json.loads(message.content)
