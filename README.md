# Khata Dost · बोलो, खाता लिखो

**A voice ledger for kirana udhaar.** The shop owner says the entry out loud while serving a customer. Khata Dost reads it back, saves it only after the owner says **"haan"**, keeps every balance, and gives the customer a receipt in their own language.

Built for **India Runs on Voice** (Scaler × Wispr Flow), Round 2 · theme: *Livelihoods and small business*.

![check](https://github.com/Blop77/khata-dost-voice/actions/workflows/check.yml/badge.svg)

## Run it (one command, no keys needed)

```bash
docker compose up --build
```

Open **http://localhost:8000**. It starts on a small labelled demo khata (Ramesh, Sunita, Ganesh).

With no keys it still works end to end:
- **Speak** in Chrome (it uses the browser's own speech recognition), or **type** in the box, or tap an example chip.
- Understanding runs on the built-in Hindi/Hinglish/Marathi rule parser.
- Replies are spoken with the phone's or laptop's own voice.

The top bar says which mode is active ("key not set" when a key is missing). CI starts this exact container with no keys on every push and checks that the main screen loads and that a typed Hindi entry is understood.

### Optional keys, for the full voice experience

Put them in a `.env` file next to `docker-compose.yml`, or export them in your shell:

| Variable | What it turns on |
|---|---|
| `SARVAM_API_KEY` | Sarvam `saaras:v4` speech-to-text (auto-detects the language) and `bulbul:v3` streaming voice replies |
| `OPENAI_API_KEY` (with `LLM_PROVIDER=openai`) | An AI reader that runs alongside the rule parser and cross-checks it. Set `OPENAI_MODEL` to choose the model; the default is `gpt-4.1-mini` |
| `ANTHROPIC_API_KEY` (with `LLM_PROVIDER=claude`) | The same, using Claude |
| `SHOP_NAME` | Shop name used in receipts and reminders (default: Sharma Store) |

Without Docker: `pip install -r requirements.txt && uvicorn app.main:app --port 8000`.

## Try these

| Say | What happens |
|---|---|
| रमेश को ढाई सौ का उधार, आटा 5 किलो, सोमवार तक | Red UDHAAR card, read back: "Ramesh, उधार 250 रुपये… लिख दूँ?" |
| हाँ | Saved. "Ramesh का कुल बाकी 750 रुपये।" The customer receipt appears with a WhatsApp button |
| Sunita ne 300 jama kiya → nahi, 400 | Only the amount changes, then it reads back again |
| Rmesh ko 50 ka udhaar | Two Rameshes, so it asks "कौन से? Ramesh, Ramesh doodhwala" |
| Mohan ko 2 packet chicks, 40 rupaye udhaar | Asks to confirm a new customer and corrects "chicks → chips" on screen |
| किस किस का पैसा बाकी है? | Speaks the top five who owe the most, and the total |
| aaj kisko yaad dilana hai | Lists who is due today, each with a polite message in that customer's language |
| पिछली entry हटाओ → हाँ | Asks first, then removes the last entry (kept for audit) |
| रमेशला अडीचशे उधार | Marathi: "Ramesh, उधार 250 रुपये. लिहू का?" |

**Hands-free confirm** is on by default. After the read-back, the app listens for "haan" on its own, so an entry takes one tap.

## Why you can trust the numbers

A ledger is money, so the design is built around not getting amounts wrong:

1. **Nothing is saved until the owner hears the entry and says yes.** A stray "haan" after some other question never saves an old draft; the app reads the entry back again first.
2. **The AI never speaks a number.** It only extracts the entry. Spoken amounts and balances come from the draft and the SQLite database, through fixed templates.
3. **Two independent readers.** The rule parser (`app/parser.py`) and the AI both read every sentence. If they disagree on the amount, the app asks ("7 रुपये या 60 रुपये? फिर से रकम बोलिए").
4. **Big amounts are also read digit by digit** ("7200 रुपये, यानी 7 2 0 0").
5. **Names match across scripts and spellings** (रमेश = Ramesh = Rmesh). If more than one customer matches, the app asks which one. A new name must be confirmed before it is used.
6. **Misheard items are corrected** against a kirana catalogue, and the correction is shown on screen.
7. **Undo always asks first.** Deleted entries are soft-deleted and kept for audit.

## Reminders, consent and privacy

- Reminders read as an **account statement from the shop**, not a collection notice. WhatsApp's policy bans debt collection.
- They go only to customers whose consent is recorded **with a timestamp**, and only between **8 am and 7 pm**.
- Each message is written in the customer's language (Hindi, Marathi or English).
- The only data stored is name, phone, language, amounts, items, due dates and the sentence that was heard. Audio is not stored.

## What is real and what is not

| Working end to end | Simulated or not built yet |
|---|---|
| Voice entry, read-back, spoken yes, corrections, undo, balances, dues, reminders (Hindi, Hinglish, Marathi, English) | Sending through the WhatsApp Business API. The prototype opens a WhatsApp share link and offers the voice note as an MP3 |
| Customer receipts in the customer's language, consent log, 8 am–7 pm rule | Reply templates for languages beyond Hindi, Marathi and English |
| Keyless mode, one-command Docker start, 33 automated tests, CI | Login, multiple shops or staff, offline queue, backups |

Demo customers are synthetic. The ledger is a single-shop SQLite file (`/data/khata.db` in Docker).

## How it works

```
mic ─▶ Sarvam saaras STT (or browser speech) ─▶ rule parser ─┐
                                                              ├─▶ merge + cross-check ─▶ conversation state ─▶ SQLite ledger
                               AI extraction (JSON schema) ───┘            │
                                                                           ▼
                                  reply from templates + DB numbers ─▶ Sarvam bulbul streaming TTS (or device voice)
```

| File | What it does |
|---|---|
| `app/parser.py` | Keyless understanding: Indian number words (ढाई सौ, dedh hazaar, saadhe teen sau, अडीचशे), names, udhaar/jama, due dates, item correction |
| `app/ledger.py` | Customers and entries in SQLite, cross-script name matching, balances, undo, who is due |
| `app/khata.py` | The conversation: draft, follow-up questions, read-back, save on yes, receipts, reminders |
| `app/main.py` | FastAPI routes, rate limits for public links, keyless start |
| `web/` | Khata Dost UI (`index.html`, `khata.js`, `khata.css`). The original generic voice starter is at `/starter.html` |
| `tests/` | Keyless tests for parsing and the conversation (`pytest`) |
| `docs/` | Pitch deck (`Khata_Dost_pitch.pdf`) and the script that builds it |

Built solo during the hackathon. The code and prompts were dictated with **Wispr Flow**.
