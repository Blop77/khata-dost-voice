"""Khata Dost: the voice conversation that turns spoken sentences into confirmed ledger entries.

Trust rules this module enforces:
- Nothing is saved until the owner hears it read back and says yes.
- Spoken numbers in replies come from the database and the draft, never from free LLM text.
- The rule parser and the LLM read every utterance; if they disagree on the amount, we ask.
"""
import json
import os
import re
from datetime import date

from app import brain, ledger, parser

SHOP = os.getenv("SHOP_NAME", "Sharma Store")
TEMPLATE_LANGS = {"hi-IN", "mr-IN", "en-IN"}
BIG_AMOUNT = 5000  # amounts above this are also read digit by digit

# One conversation per browser tab. In-memory is fine for a single-shop prototype.
SESSIONS: dict[str, dict] = {}


def session(sid: str) -> dict:
    return SESSIONS.setdefault(sid, {"draft": None, "awaiting": None, "options": [], "lang": "hi-IN", "turns": 0})


def prefer_language(sid: str, ui_lang: str | None) -> None:
    """A fresh conversation starts in the screen's language (the Hindi/English switch)."""
    sess = session(sid)
    if ui_lang in TEMPLATE_LANGS and not sess.get("turns"):
        sess["lang"] = ui_lang


# --- what we say ------------------------------------------------------------------------

DAYS = {"hi-IN": ["सोमवार", "मंगलवार", "बुधवार", "गुरुवार", "शुक्रवार", "शनिवार", "रविवार"],
        "mr-IN": ["सोमवार", "मंगळवार", "बुधवार", "गुरुवार", "शुक्रवार", "शनिवार", "रविवार"],
        "en-IN": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]}
MONTHS = {"hi-IN": "जनवरी फ़रवरी मार्च अप्रैल मई जून जुलाई अगस्त सितंबर अक्टूबर नवंबर दिसंबर".split(),
          "mr-IN": "जानेवारी फेब्रुवारी मार्च एप्रिल मे जून जुलै ऑगस्ट सप्टेंबर ऑक्टोबर नोव्हेंबर डिसेंबर".split(),
          "en-IN": "January February March April May June July August September October November December".split()}
TYPE = {"hi-IN": {"udhaar": "उधार", "jama": "जमा"}, "mr-IN": {"udhaar": "उधार", "jama": "जमा"},
        "en-IN": {"udhaar": "credit", "jama": "paid"}}
TYPE_BEFORE = {"hi-IN": TYPE["hi-IN"], "mr-IN": TYPE["mr-IN"], "en-IN": {"udhaar": "credit of", "jama": "paid"}}

T = {
    "readback": {"hi-IN": "{name}, {type} {amount}{items}{due}। लिख दूँ?",
                 "mr-IN": "{name}, {type} {amount}{items}{due}. लिहू का?",
                 "en-IN": "{name}, {type} {amount}{items}{due}. Shall I save it?"},
    "due": {"hi-IN": ", {day} {d} {month} तक", "mr-IN": ", {day} {d} {month} पर्यंत", "en-IN": ", due {day} {d} {month}"},
    "saved": {"hi-IN": "लिख दिया। {name} का कुल बाकी {balance}।", "mr-IN": "लिहिले. {name} यांचे एकूण बाकी {balance}.",
              "en-IN": "Saved. {name} now owes {balance} in total."},
    "saved_clear": {"hi-IN": "लिख दिया। {name} का पूरा हिसाब साफ़ है।", "mr-IN": "लिहिले. {name} यांचा हिशोब पूर्ण झाला.",
                    "en-IN": "Saved. {name} has no dues left."},
    "saved_advance": {"hi-IN": "लिख दिया। {name} का {balance} आपके पास जमा है।",
                      "mr-IN": "लिहिले. {name} यांचे {balance} आगाऊ जमा आहेत.",
                      "en-IN": "Saved. You hold {balance} in advance for {name}."},
    "new_customer": {"hi-IN": " नया ग्राहक जुड़ा।", "mr-IN": " नवीन ग्राहक जोडला.", "en-IN": " New customer added."},
    "ask_amount": {"hi-IN": "{name} को कितने का?", "mr-IN": "{name} यांना किती रुपये?", "en-IN": "How much for {name}?"},
    "ask_type": {"hi-IN": "{name} को उधार दिया या पैसे मिले?", "mr-IN": "{name} यांना उधार दिले की पैसे मिळाले?",
                 "en-IN": "Did {name} take credit or pay you?"},
    "ask_name": {"hi-IN": "किसके नाम लिखूँ?", "mr-IN": "कोणाच्या नावावर लिहू?", "en-IN": "Whose account is this for?"},
    "which": {"hi-IN": "कौन से? {options}", "mr-IN": "कोणते? {options}", "en-IN": "Which one? {options}"},
    "confirm_new": {"hi-IN": "{name} नया ग्राहक है। सही?", "mr-IN": "{name} नवीन ग्राहक आहेत. बरोबर?",
                    "en-IN": "{name} is a new customer. Correct?"},
    "amount_check": {"hi-IN": "{a} या {b}? फिर से रकम बोलिए।", "mr-IN": "{a} की {b}? पुन्हा रक्कम सांगा.",
                     "en-IN": "{a} or {b}? Please say the amount again."},
    "cancelled": {"hi-IN": "ठीक है, नहीं लिखा।", "mr-IN": "ठीक आहे, लिहिले नाही.", "en-IN": "Okay, not saved."},
    "dues_none": {"hi-IN": "किसी का पैसा बाकी नहीं है।", "mr-IN": "कोणाचेही पैसे बाकी नाहीत.", "en-IN": "Nobody owes you anything."},
    "dues": {"hi-IN": "{count} लोगों के कुल {total} बाकी। {top}।", "mr-IN": "{count} जणांचे एकूण {total} बाकी. {top}.",
             "en-IN": "{count} people owe you {total} in total. {top}."},
    "customer": {"hi-IN": "{name} का कुल बाकी {balance}।{last}", "mr-IN": "{name} यांचे एकूण बाकी {balance}.{last}",
                 "en-IN": "{name} owes {balance} in total.{last}"},
    "customer_last": {"hi-IN": " आख़िरी: {amount} {type}।", "mr-IN": " शेवटचे: {amount} {type}.", "en-IN": " Last: {amount} {type}."},
    "unknown_customer": {"hi-IN": "{name} नाम का कोई ग्राहक नहीं मिला।", "mr-IN": "{name} नावाचा ग्राहक सापडला नाही.",
                         "en-IN": "I couldn't find a customer called {name}."},
    "undo_confirm": {"hi-IN": "{name} का {amount} {type} हटाऊँ?", "mr-IN": "{name} यांचे {amount} {type} काढू का?",
                     "en-IN": "Remove {name}'s {amount} {type}?"},
    "undone": {"hi-IN": "हटा दिया। {name} का बाकी अब {balance}।", "mr-IN": "काढले. {name} यांचे बाकी आता {balance}.",
               "en-IN": "Removed. {name} now owes {balance}."},
    "nothing_to_undo": {"hi-IN": "हटाने को कोई एंट्री नहीं है।", "mr-IN": "काढण्यासाठी नोंद नाही.", "en-IN": "There is nothing to remove."},
    "reminders_none": {"hi-IN": "आज किसी की तारीख़ नहीं है।", "mr-IN": "आज कोणाचीही तारीख नाही.", "en-IN": "Nobody is due today."},
    "reminders": {"hi-IN": "{count} लोगों की तारीख़ आ गई: {names}। स्क्रीन पर भेजने का बटन है।",
                  "mr-IN": "{count} जणांची तारीख आली: {names}. पाठवण्याचे बटण स्क्रीनवर आहे.",
                  "en-IN": "{count} people are due: {names}. Send buttons are on screen."},
    "one_at_a_time": {"hi-IN": "एक-एक करके बोलिए। पहले {name} का बताइए।", "mr-IN": "एकेक करून सांगा. आधी {name} यांचे सांगा.",
                      "en-IN": "One at a time, please. Tell me {name}'s entry first."},
    "which_new": {"hi-IN": "{old} या नया ग्राहक {new}?", "mr-IN": "{old} की नवीन ग्राहक {new}?", "en-IN": "{old}, or a new customer {new}?"},
    "unclear": {"hi-IN": "समझ नहीं आया। ऐसे बोलिए: रमेश को ढाई सौ का उधार।",
                "mr-IN": "समजले नाही. असे सांगा: रमेशला अडीचशे उधार.",
                "en-IN": "Sorry, I didn't get that. Try: Ramesh, 250 credit."},
    "not_heard": {"hi-IN": "आवाज़ साफ़ नहीं आई, फिर से बोलिए।", "mr-IN": "आवाज स्पष्ट आला नाही, पुन्हा सांगा.",
                  "en-IN": "I couldn't hear that clearly, please say it again."},
}

REMINDER = {
    "hi-IN": "{name} जी, नमस्ते। {shop} में आपका {balance} बाकी है{due}। सुविधा हो तो चुका दीजिए। धन्यवाद। (ये मैसेज बंद करने के लिए \"बंद\" लिखें)",
    "mr-IN": "{name} जी, नमस्कार. {shop} मध्ये तुमचे {balance} बाकी आहे{due}. सोयीने भरा. धन्यवाद. (हे मेसेज बंद करण्यासाठी \"बंद\" लिहा)",
    "en-IN": "Namaste {name} ji. Your balance at {shop} is {balance}{due}. Please pay when convenient. Thank you. (Reply STOP to stop these messages)",
}
RECEIPT = {
    "hi-IN": "{name} जी, {shop} में आज {amount} {type} लिखा गया। कुल बाकी {balance}।",
    "mr-IN": "{name} जी, {shop} मध्ये आज {amount} {type} लिहिले. एकूण बाकी {balance}.",
    "en-IN": "{name} ji, {shop} recorded {amount} {type} today. Total due {balance}.",
}


def lang_of(code: str | None) -> str:
    return code if code in TEMPLATE_LANGS else "hi-IN"


def rupees(amount: int, lang: str, spell: bool = False) -> str:
    word = {"hi-IN": "रुपये", "mr-IN": "रुपये", "en-IN": "rupees"}[lang]
    text = f"{amount:,} {word}".replace(",", "") if lang != "en-IN" else f"{amount:,} {word}"
    if spell and amount > BIG_AMOUNT:  # misheard zeros cost real money: read big amounts digit by digit too
        text += {"hi-IN": ", यानी ", "mr-IN": ", म्हणजे ", "en-IN": ", that is "}[lang] + " ".join(str(amount))
    return text


def say(key: str, lang: str, **kw) -> str:
    return T[key][lang_of(lang)].format(**kw)


def due_phrase(iso: str | None, lang: str, template: str = "due") -> str:
    if not iso:
        return ""
    d = date.fromisoformat(iso)
    lang = lang_of(lang)
    return T[template][lang].format(day=DAYS[lang][d.weekday()], d=d.day, month=MONTHS[lang][d.month - 1])


def readback(draft: dict, lang: str) -> str:
    items = f", {draft['items']}" if draft.get("items") else ""
    return say("readback", lang, name=draft["name"], amount=rupees(draft["amount"], lang_of(lang), spell=True),
               type=TYPE_BEFORE[lang_of(lang)][draft["type"]], items=items, due=due_phrase(draft.get("due_date"), lang))


def reminder_text(customer: dict) -> str:
    lang = lang_of(customer.get("language"))
    due = ""
    if customer.get("due_date"):
        due = {"hi-IN": " ({d} तक का वादा था)", "mr-IN": " ({d} पर्यंत भरायचे होते)", "en-IN": " (promised by {d})"}[lang].format(
            d=due_phrase(customer["due_date"], lang).lstrip(", ").replace(" तक", "").replace(" पर्यंत", "").replace("due ", ""))
    return REMINDER[lang].format(name=customer["name"], shop=SHOP, balance=rupees(customer["balance"], lang), due=due)


def receipt_text(customer: dict, entry: dict, balance: int) -> str:
    lang = lang_of(customer.get("language"))
    return RECEIPT[lang].format(name=customer["name"], shop=SHOP, amount=rupees(entry["amount"], lang),
                                type=TYPE[lang][entry["type"]], balance=rupees(max(balance, 0), lang))


# --- understanding ------------------------------------------------------------------------

SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {"type": "string", "enum": ["entry", "confirm", "cancel", "correct", "dues_query",
                                              "customer_query", "undo", "reminders", "unclear"]},
        "customer_name": {"type": ["string", "null"], "description": "Customer name exactly as spoken, e.g. Ramesh or रमेश"},
        "entry_type": {"type": ["string", "null"], "enum": ["udhaar", "jama", None],
                       "description": "udhaar = goods/money given on credit; jama = customer paid back"},
        "amount_rupees": {"type": ["integer", "null"], "description": "Rupees as an integer. dhai sau=250, dedh hazaar=1500"},
        "items": {"type": ["string", "null"], "description": "Short item list in Roman script, corrected to real kirana items"},
        "due_date": {"type": ["string", "null"], "description": "YYYY-MM-DD promised payment date, or null"},
        "language": {"type": "string", "description": "BCP-47 code of the language the owner spoke, e.g. hi-IN, mr-IN, ta-IN, en-IN"},
    },
    "required": ["intent", "customer_name", "entry_type", "amount_rupees", "items", "due_date", "language"],
    "additionalProperties": False,
}


def _system(sess: dict) -> str:
    today = date.today()
    names = [c["name"] for c in ledger.customers_with_balance()][:60]
    return f"""You read what a kirana (Indian grocery) shop owner says to their voice ledger and return one JSON object.
Today is {today.strftime('%A')} {today.isoformat()}. Known customers: {json.dumps(names, ensure_ascii=False)}.
Pending unsaved entry: {json.dumps(sess.get('draft'), ensure_ascii=False)}. The app is waiting for: {sess.get('awaiting') or 'a new command'}.

Intents:
- entry: a new udhaar (credit) or jama (payment) line, e.g. "Ramesh ko dhai sau ka udhaar", "Suresh ne 500 jama kiya".
- confirm: yes to the pending entry (haan, ha, ok, likh do, theek hai, barobar).
- cancel: no, without new details. correct: no/changes WITH a new detail ("nahi, teen sau", "jama tha").
- dues_query: who owes money ("kis kis ka paisa baaki hai"). customer_query: one person's balance ("Ramesh ka hisaab").
- undo: remove the last saved entry ("pichli entry hatao"). reminders: who to remind today ("aaj kisko yaad dilana hai").
- unclear: anything else, or speech that makes no sense.

Rules:
- Never invent an amount. If no amount was said, amount_rupees is null. Quantities like "5 kilo" or "2 packet" are not amounts.
- Convert Indian number words: sau=100, hazaar=1000, dhai=2.5x, dedh=1.5x, sawa=1.25x, saadhe=+0.5, paune=-0.25, Marathi adeechshe=250.
- Speech recognition may mishear item names ("chicks packet" is "chips packet"); correct items to the likely kirana product.
- Keep customer_name as spoken; do not translate or invent surnames. Return only fields from THIS utterance (use null otherwise).
- Resolve relative dates (Monday/somvar, kal tak, parso, agle hafte, mahine ke end) to YYYY-MM-DD after today."""


async def understand(sess: dict, text: str) -> tuple[dict, dict | None]:
    rules = parser.understand(text, has_draft=bool(sess.get("draft")))
    try:
        ai = await brain.extract(_system(sess), [{"role": "user", "content": text}], SCHEMA, "ledger_turn")
    except Exception:  # network or quota trouble: keep working on rules alone
        ai = None
    return rules, ai


def clean_name(name: str | None) -> str | None:
    """Drop honorifics the model sometimes keeps: "Ramesh bhai" -> "Ramesh", "Sunita ji" -> "Sunita"."""
    if not name:
        return name
    words = [w for w in name.split() if w.lower().strip(".,") not in parser.HONORIFIC]
    return " ".join(words) or name


def merge(rules: dict, ai: dict | None) -> dict:
    if not ai:
        return {**rules, "source": "rules"}
    out = {"source": "ai+rules", "item_fixes": rules.get("item_fixes", []), "language": ai.get("language")}
    out["intent"] = ai["intent"]
    # a bare yes/no is unambiguous: trust the rules if the model hedges
    if rules["intent"] in ("confirm", "cancel") and ai["intent"] in ("unclear", "entry"):
        out["intent"] = rules["intent"]
    if ai["intent"] == "confirm" and rules["intent"] != "confirm":
        out["intent"] = "correct" if rules["intent"] in ("correct", "entry") else rules["intent"]
    if rules["intent"] == "multiple":
        out["intent"] = "multiple"
    for k in ("customer_name", "entry_type", "items", "due_date"):
        out[k] = ai.get(k) or rules.get(k)
    out["customer_name"] = clean_name(out["customer_name"])
    if ai["intent"] == "cancel" and rules["intent"] == "correct":
        out["intent"] = "correct"  # "nahi nahi, Ganesh" changes the name; it doesn't cancel
    a, r = ai.get("amount_rupees"), rules.get("amount_rupees")
    out["amount_rupees"] = a if a else r
    if a and r and a != r:
        out["amount_conflict"] = sorted({a, r})
    return out


# --- the conversation ---------------------------------------------------------------------

def _reply(sess: dict, text: str, **extra) -> dict:
    return {"reply": text, "lang": sess["lang"], "draft": sess.get("draft"), "awaiting": sess.get("awaiting"),
            "options": sess.get("options", []), **extra}


def _resolve_customer(sess: dict) -> dict | None:
    """Sets draft customer_id, or asks which customer / confirms a new one. Returns a reply if we must ask."""
    draft, lang = sess["draft"], sess["lang"]
    if draft.get("customer_id") or draft.get("new_customer"):
        return None
    matches = ledger.find_customers(draft["name"])
    if len(matches) == 1 and ledger.name_key(matches[0]["name"]).split(" ")[0] != ledger.name_key(draft["name"]).split(" ")[0]:
        # "Sunil" sounds like "Sunita": never move money to a different person silently
        sess["awaiting"] = "which_customer"
        sess["options"] = [{"id": matches[0]["id"], "name": matches[0]["name"]}, {"id": None, "name": draft["name"], "new": True}]
        return _reply(sess, say("which_new", lang, old=matches[0]["name"], new=draft["name"]))
    if len(matches) == 1:
        draft["customer_id"], draft["name"] = matches[0]["id"], matches[0]["name"]
        return None
    if len(matches) > 1:
        sess["awaiting"], sess["options"] = "which_customer", [{"id": m["id"], "name": m["name"]} for m in matches[:3]]
        return _reply(sess, say("which", lang, options=", ".join(m["name"] for m in matches[:3])))
    sess["awaiting"] = "confirm_new_customer"
    return _reply(sess, say("confirm_new", lang, name=draft["name"]))


def pick_option(text: str, options: list[dict]) -> dict | None:
    """Which of the offered customers did the owner mean? "doodhwala", "दूधवाला", "pehla", or the full name."""
    import difflib
    said = ledger.name_key(text)
    if not said or not options:
        return None
    new_opt = next((o for o in options if o.get("new")), None)
    if new_opt and re.search(r"naya|naye|नया|नए|new|नवीन|navin", text.lower()):
        return new_opt
    if re.search(r"pehl|पहल|first|pahil|पहिल", text.lower()):
        return options[0]
    if re.search(r"dusr|दूसर|second|dusra", text.lower()) and len(options) > 1:
        return options[1]
    best, best_score = None, 0.0
    for opt in options:
        key = ledger.name_key(opt["name"])
        parts = key.split()
        # Distinguishing words count most: "doodhwala" picks "Ramesh doodhwala", not plain "Ramesh".
        candidates = [key] + parts[1:] + ([parts[0]] if len(parts) == 1 else [])
        score = max(difflib.SequenceMatcher(None, said, c).ratio() for c in candidates)
        if score > best_score:
            best, best_score = opt, score
    return best if best_score >= 0.72 else None


def _same_person(a: str, b: str) -> bool:
    ka, kb = ledger.name_key(a), ledger.name_key(b)
    return ka == kb or ka.split(" ")[0] == kb.split(" ")[0]


def session_reply(sid: str, key: str) -> dict:
    sess = session(sid)
    return _reply(sess, say(key, sess["lang"]))


def _next_question(sess: dict) -> dict:
    """Ask for the first missing piece, else read the entry back for confirmation."""
    d, lang = sess["draft"], sess["lang"]
    if not d.get("name"):
        sess["awaiting"] = "name"
        return _reply(sess, say("ask_name", lang))
    if (asked := _resolve_customer(sess)) is not None:
        return asked
    if not d.get("amount"):
        sess["awaiting"] = "amount"
        return _reply(sess, say("ask_amount", lang, name=d["name"]))
    if not d.get("type"):
        sess["awaiting"] = "type"
        return _reply(sess, say("ask_type", lang, name=d["name"]))
    sess["awaiting"] = "confirm"
    return _reply(sess, readback(d, lang))


def _apply(draft: dict, u: dict) -> None:
    if u.get("customer_name") and u["customer_name"] != draft.get("name"):
        draft.update(name=u["customer_name"], customer_id=None, new_customer=False)
    for src, dst in (("amount_rupees", "amount"), ("entry_type", "type"), ("items", "items"), ("due_date", "due_date")):
        if u.get(src):
            draft[dst] = u[src]


def _save(sess: dict, heard: str) -> dict:
    d, lang = sess["draft"], sess["lang"]
    new = False
    if not d.get("customer_id"):
        c = ledger.add_customer(d["name"], language=lang)
        d["customer_id"], new = c["id"], True
    entry = ledger.add_entry(d["customer_id"], d["type"], d["amount"], d.get("items"), d.get("due_date"), heard)
    bal = ledger.balance(d["customer_id"])
    customer = ledger.customer_detail(d["customer_id"])
    if bal > 0:
        text = say("saved", lang, name=d["name"], balance=rupees(bal, lang_of(lang)))
    elif bal == 0:
        text = say("saved_clear", lang, name=d["name"])
    else:
        text = say("saved_advance", lang, name=d["name"], balance=rupees(-bal, lang_of(lang)))
    if new:
        text += T["new_customer"][lang_of(lang)]
    sess.update(draft=None, awaiting=None, options=[])
    return _reply(sess, text, saved={"entry": entry, "balance": bal, "customer": customer,
                                     "receipt": receipt_text(customer, entry, bal)})


async def handle(sid: str, text: str, language_code: str | None = None) -> dict:
    sess = session(sid)
    text = (text or "").strip()
    if not text:
        return _reply(sess, say("not_heard", sess["lang"]))

    sess["turns"] = sess.get("turns", 0) + 1
    rules, ai = await understand(sess, text)
    u = merge(rules, ai)
    # Short replies ("haan", "nahi, 400", "doodhwala") say little about language: keep the conversation's.
    if len(parser.tokens(text)) >= 3:
        guess = parser.script_language(text)
        # plain English with no Hindi words is unambiguous; otherwise trust speech recognition, then the model
        sess["lang"] = lang_of("en-IN" if guess == "en-IN" and not language_code else
                               language_code or u.get("language") or guess)
    lang, awaiting = sess["lang"], sess.get("awaiting")
    meta = {"source": u["source"], "item_fixes": u.get("item_fixes") or [], "heard": text}

    # A different customer's name means a brand-new entry: never carry the old draft's items or amount over.
    draft = sess.get("draft")
    if (draft and draft.get("name") and u.get("customer_name") and u["intent"] in ("entry", "unclear")
            and awaiting not in ("name", "which_customer", "confirm_new_customer")
            and not _same_person(draft["name"], u["customer_name"])):
        sess.update(draft={"name": None, "heard": text}, awaiting=None, options=[])
        awaiting = None

    # Questions the app asked last time take priority over fresh intent guesses.
    if awaiting == "amount_check":
        if u.get("amount_rupees"):
            sess["draft"]["amount"] = u["amount_rupees"]
            return {**_next_question(sess), **meta}
    if awaiting == "which_customer":
        opt = pick_option(text, sess["options"])
        if opt and opt.get("new"):
            sess["draft"].update(customer_id=None, name=opt["name"], new_customer=True)
            sess["options"] = []
            return {**_next_question(sess), **meta}
        if opt:
            sess["draft"].update(customer_id=opt["id"], name=opt["name"])
            sess["options"] = []
            return {**_next_question(sess), **meta}
        if u["intent"] not in ("dues_query", "customer_query", "undo", "reminders", "cancel") and not u.get("amount_rupees"):
            names = ", ".join(o["name"] for o in sess["options"])
            return {**_reply(sess, say("which", lang, options=names)), **meta}
    if awaiting == "confirm_new_customer":
        if u["intent"] == "confirm" or parser.is_yes(text):
            sess["draft"]["new_customer"] = True
            return {**_next_question(sess), **meta}
        if parser.is_no(text) and not u.get("customer_name"):
            sess["draft"]["name"] = None
            sess["awaiting"] = "name"
            return {**_reply(sess, say("ask_name", lang)), **meta}
        if u.get("customer_name") and not _same_person(u["customer_name"], sess["draft"]["name"]):
            # "nahi nahi, Ganesh": same entry, different person
            sess["draft"].update(name=u["customer_name"], customer_id=None, new_customer=False)
            _apply(sess["draft"], {k: v for k, v in u.items() if k != "customer_name"})
            sess["awaiting"] = None
            return {**_next_question(sess), **meta}
        if any(u.get(k) for k in ("amount_rupees", "entry_type", "items", "due_date")) and not u.get("customer_name"):
            _apply(sess["draft"], u)  # keep the extra detail, but still need a yes on the new name
            return {**_reply(sess, say("confirm_new", lang, name=sess["draft"]["name"])), **meta}
    if awaiting == "undo_confirm":
        sess["awaiting"] = None
        if u["intent"] == "confirm" or parser.is_yes(text):
            gone = ledger.undo_last()
            if gone:
                return {**_reply(sess, say("undone", lang, name=gone["name"],
                                           balance=rupees(max(ledger.balance(gone["customer_id"]), 0), lang))),
                        **meta, "undone": gone}
        return {**_reply(sess, say("cancelled", lang)), **meta}
    if awaiting in ("amount", "type", "name") and sess.get("draft") and u["intent"] in ("entry", "correct", "unclear"):
        if awaiting == "name" and not u.get("customer_name") and u["intent"] == "unclear":
            u["customer_name"] = text.strip(" ।.?")
        _apply(sess["draft"], u)
        return {**_next_question(sess), **meta}

    intent = u["intent"]
    if intent == "multiple":
        return {**_reply(sess, say("one_at_a_time", lang, name=u.get("customer_name") or "")), **meta}
    if intent == "confirm" and sess.get("draft") and awaiting == "confirm":
        return {**_save(sess, sess["draft"].get("heard", text)), **meta}
    if intent == "confirm" and sess.get("draft"):
        # A yes that isn't answering a read-back (e.g. after a balance question) never saves silently.
        return {**_next_question(sess), **meta}
    if intent == "cancel" and sess.get("draft"):
        sess.update(draft=None, awaiting=None, options=[])
        return {**_reply(sess, say("cancelled", lang)), **meta}
    if intent in ("entry", "correct") and (u.get("amount_rupees") or u.get("entry_type") or u.get("customer_name")):
        if intent == "entry" and u.get("customer_name") and (not sess.get("draft") or awaiting != "confirm"):
            sess["draft"] = {"name": None, "heard": text}
        sess["draft"] = sess.get("draft") or {"name": None, "heard": text}
        _apply(sess["draft"], u)
        if u.get("amount_conflict"):
            a, b = u["amount_conflict"]
            sess["awaiting"] = "amount_check"
            return {**_reply(sess, say("amount_check", lang, a=rupees(a, lang), b=rupees(b, lang))), **meta}
        return {**_next_question(sess), **meta}
    if intent in ("dues_query", "customer_query", "undo", "reminders") and awaiting == "confirm":
        sess["awaiting"] = None  # the read-back is stale now; it must be heard again before saving
    if intent == "dues_query":
        owing = [c for c in ledger.customers_with_balance() if c["balance"] > 0]
        if not owing:
            return {**_reply(sess, say("dues_none", lang)), **meta, "view": "dues"}
        top = ", ".join(f"{c['name']} {rupees(c['balance'], lang)}" for c in owing[:5])
        total = sum(c["balance"] for c in owing)
        return {**_reply(sess, say("dues", lang, count=len(owing), total=rupees(total, lang), top=top)), **meta,
                "view": "dues", "dues": owing}
    if intent == "customer_query":
        matches = ledger.find_customers(u.get("customer_name") or "")
        if not matches:
            return {**_reply(sess, say("unknown_customer", lang, name=u.get("customer_name") or "")), **meta}
        c = ledger.customer_detail(matches[0]["id"])
        last = ""
        if c["entries"]:
            e = c["entries"][0]
            last = T["customer_last"][lang].format(amount=rupees(e["amount"], lang), type=TYPE[lang][e["type"]])
        return {**_reply(sess, say("customer", lang, name=c["name"], balance=rupees(max(c["balance"], 0), lang), last=last)),
                **meta, "view": "customer", "customer": c}
    if intent == "undo":
        last = ledger.recent_entries(1)
        if not last:
            return {**_reply(sess, say("nothing_to_undo", lang)), **meta}
        e = last[0]
        sess["awaiting"] = "undo_confirm"
        return {**_reply(sess, say("undo_confirm", lang, name=e["name"], amount=rupees(e["amount"], lang),
                                   type=TYPE[lang][e["type"]])), **meta}
    if intent == "reminders":
        due = ledger.due_customers()
        if not due:
            return {**_reply(sess, say("reminders_none", lang)), **meta, "view": "reminders", "reminders": []}
        return {**_reply(sess, say("reminders", lang, count=len(due), names=", ".join(c["name"] for c in due))),
                **meta, "view": "reminders", "reminders": reminders()}
    if sess.get("draft") and awaiting == "confirm":
        return {**_reply(sess, readback(sess["draft"], lang)), **meta}
    return {**_reply(sess, say("unclear", lang)), **meta}


def reminder_window_open(now=None) -> bool:
    """Reminders go out 8 am - 7 pm only (the RBI fair-practice hours, adopted voluntarily)."""
    from datetime import datetime
    return 8 <= (now or datetime.now()).hour < 19


def reminders() -> list[dict]:
    """Everyone due today or earlier, with a ready-to-send message in the customer's language."""
    out = []
    for c in ledger.due_customers():
        text = reminder_text(c)
        out.append({"customer_id": c["id"], "name": c["name"], "balance": c["balance"], "due_date": c["due_date"],
                    "phone": c["phone"], "consent": bool(c["reminder_consent"]), "language": lang_of(c["language"]),
                    "text": text})
    return out
