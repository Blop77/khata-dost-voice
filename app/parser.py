"""Rule-based understanding of kirana ledger speech (Hindi, Hinglish, a little Marathi and English).

Runs with no API key. It is also a second opinion on the LLM: if the two disagree on an
amount, the app asks the owner instead of guessing.
"""
import difflib
import re
from datetime import date, timedelta

# --- numbers -----------------------------------------------------------------------------

UNITS = {
    "ek": 1, "एक": 1, "do": 2, "दो": 2, "teen": 3, "tin": 3, "तीन": 3, "char": 4, "chaar": 4, "चार": 4,
    "paanch": 5, "panch": 5, "pach": 5, "पांच": 5, "पाँच": 5, "chhe": 6, "chhah": 6, "che": 6, "छह": 6, "छः": 6,
    "saat": 7, "सात": 7, "aath": 8, "आठ": 8, "nau": 9, "नौ": 9, "das": 10, "दस": 10,
    "gyarah": 11, "ग्यारह": 11, "barah": 12, "baarah": 12, "बारह": 12, "pandrah": 15, "पंद्रह": 15,
    "bees": 20, "बीस": 20, "pachchis": 25, "pachees": 25, "पच्चीस": 25, "tees": 30, "तीस": 30,
    "chalis": 40, "chaalis": 40, "चालीस": 40, "pachas": 50, "pachaas": 50, "पचास": 50,
    "saath": 60, "साठ": 60, "sattar": 70, "सत्तर": 70, "assi": 80, "अस्सी": 80, "nabbe": 90, "नब्बे": 90,
}
SCALES = {"sau": 100, "सौ": 100, "hazaar": 1000, "hazar": 1000, "hajar": 1000, "हज़ार": 1000, "हजार": 1000,
          "lakh": 100000, "लाख": 100000, "hundred": 100, "thousand": 1000}
# "dhai sau" = 250, "dedh hazaar" = 1500, "sawa sau" = 125, "paune do sau" = 175, "saadhe teen sau" = 350
FRACTIONS = {"dhai": 2.5, "dhaai": 2.5, "ढाई": 2.5, "dedh": 1.5, "derh": 1.5, "डेढ़": 1.5, "डेढ": 1.5,
             "sawa": 1.25, "sava": 1.25, "सवा": 1.25, "adeech": 2.5, "अडीच": 2.5}
MODIFIERS = {"saadhe": 0.5, "sadhe": 0.5, "साढ़े": 0.5, "साढे": 0.5, "paune": -0.25, "पौने": -0.25}
# Marathi compounds such as "अडीचशे" (2.5 x 100) or "पाचशे" (5 x 100)
MARATHI_SHE = re.compile(r"^(.+?)(?:शे|she)$")

# Quantities of goods, not money: "aata 5 kilo", "2 packet chips"
QTY_UNITS = {"kg", "kilo", "kilos", "किलो", "g", "gm", "gram", "ग्राम", "litre", "liter", "ltr", "l", "लीटर",
             "packet", "packets", "pkt", "पैकेट", "dozen", "darjan", "दर्जन", "piece", "pcs", "पीस", "bori", "बोरी",
             "ml", "box", "dabba", "डिब्बा", "bottle", "botal", "बोतल"}
MONEY_MARKERS = {"rupaye", "rupees", "rupee", "rupay", "rs", "रुपये", "रुपए", "रूपये", "ka", "ki", "ke", "का", "की",
                 "के", "udhaar", "udhar", "उधार", "jama", "जमा", "रुपयांचे", "रुपये", "चे"}

TOKEN = re.compile(r"₹?\s?\d[\d,]*(?:\.\d+)?|[\wऀ-ॿ]+", re.UNICODE)


def tokens(text: str) -> list[str]:
    return [t.replace("₹", "").replace(",", "").strip().lower() for t in TOKEN.findall(text)]


def _word_value(tok: str) -> float | None:
    if re.fullmatch(r"\d+(?:\.\d+)?", tok):
        return float(tok)
    return UNITS.get(tok)


def find_amounts(text: str) -> list[dict]:
    """All money-like numbers in order: [{"value": int, "start": token index, "money": bool}]."""
    toks = tokens(text)
    found, i = [], 0
    while i < len(toks):
        start, total, current, frac, mod, used = i, 0.0, 0.0, None, 0.0, False
        while i < len(toks):
            tok = toks[i]
            she = MARATHI_SHE.match(tok)
            if tok in FRACTIONS:
                frac = FRACTIONS[tok]
            elif tok in MODIFIERS:
                mod = MODIFIERS[tok]
            elif _word_value(tok) is not None:
                if current and re.fullmatch(r"[\d.]+", tok):
                    break  # two separate numbers in a row, e.g. "250 5"
                current += _word_value(tok)
            elif tok in SCALES:
                base = frac if frac is not None else (current + mod if current else (1 + mod if mod else 1))
                if SCALES[tok] == 100:
                    current = base * 100
                else:
                    total += base * SCALES[tok]
                    current = 0.0
                frac, mod = None, 0.0
            elif she and (she.group(1) in FRACTIONS or she.group(1) in UNITS or she.group(1) in {"पाच", "पंधरा"}):
                head = she.group(1)
                base = FRACTIONS.get(head) or UNITS.get(head) or {"पाच": 5, "पंधरा": 15}[head]
                current = base * 100
            else:
                break
            used = True
            i += 1
        if used:
            value = total + current
            if value > 0:
                nxt = toks[i] if i < len(toks) else ""
                prev = toks[start - 1] if start > 0 else ""
                is_qty = nxt in QTY_UNITS
                money = (not is_qty) and (nxt in MONEY_MARKERS or prev in MONEY_MARKERS or value >= 10
                                          or any(t in SCALES or t in FRACTIONS for t in toks[start:i]))
                found.append({"value": int(round(value)), "start": start, "money": money, "qty": is_qty})
        else:
            i += 1
    return found


def parse_amount(text: str) -> int | None:
    money = [a for a in find_amounts(text) if a["money"]]
    return money[0]["value"] if money else None


# --- intent words ------------------------------------------------------------------------

def _has(text: str, words) -> bool:
    low = f" {text.lower()} "
    return any(f" {w} " in low or (len(w) > 3 and w in low) for w in words)


UDHAAR = ["udhaar", "udhar", "udhari", "उधार", "उधारी", "credit", "baaki likh", "likh lo", "khate me", "khate mein",
          "खाते में", "le gaya", "le gayi", "ले गया", "ले गई", "दिया उधार"]
JAMA = ["jama", "जमा", "paid", "payment", "de gaya", "de gayi", "दे गया", "दे गई", "diye", "दिए", "लौटाए", "lautaye",
        "chukaya", "चुकाया", "wapas", "वापस", "mile", "मिले", "bhar diya", "भर दिया"]
YES = ["haan", "han", "ha", "haa", "हाँ", "हां", "हा", "ok", "okay", "ओके", "theek", "thik", "ठीक", "sahi", "सही",
       "likh do", "likho", "लिख दो", "लिखो", "yes", "ji", "जी", "ho", "हो", "बरोबर", "barobar", "save"]
NO = ["nahi", "nahin", "नहीं", "नही", "na", "ना", "no", "galat", "गलत", "mat", "मत", "cancel", "रहने दो", "rehne do", "nako", "नको"]
DUES = ["kis kis", "किस किस", "किस-किस", "kiska kiska", "sabka hisaab", "सबका हिसाब", "kaun kaun", "कौन कौन",
        "list", "लिस्ट", "baaki hai", "बाकी है", "बाकी हैं", "who owes", "dues", "kitne log"]
CUSTOMER_QUERY = ["ka hisaab", "का हिसाब", "kitna baaki", "कितना बाकी", "kitne baaki", "कितने बाकी", "ka khata",
                  "का खाता", "chi baki", "ची बाकी", "balance"]
UNDO = ["undo", "pichli entry", "पिछली entry", "पिछली एंट्री", "last entry", "galat entry", "गलत एंट्री", "hatao",
        "हटाओ", "mita do", "मिटा दो", "delete"]
REMIND = ["yaad dila", "याद दिला", "reminder", "रिमाइंडर", "message bhej", "मैसेज भेज", "sabko bhej", "सबको भेज"]


def is_yes(text: str) -> bool:
    toks = tokens(text)
    return 0 < len(toks) <= 4 and _has(text, YES) and not _has(text, NO)


def is_no(text: str) -> bool:
    return _has(text, NO)


# --- names -------------------------------------------------------------------------------

STOP = set(UNITS) | set(SCALES) | set(FRACTIONS) | set(MODIFIERS) | QTY_UNITS | {
    "ko", "को", "ne", "ने", "ka", "ki", "ke", "का", "की", "के", "se", "से", "aur", "और", "tak", "तक", "hai", "है",
    "ji", "जी", "bhai", "भाई", "bhaiya", "भैया", "aaj", "आज", "kal", "कल", "abhi", "अभी", "mera", "मेरा", "likh",
    "लिख", "do", "दो", "la", "ला", "ना", "नी", "ni", "chi", "ची", "रुपये", "rupaye", "rs", "kya", "क्या",
    "kis", "किस", "kiska", "किसका", "kaun", "कौन", "paisa", "पैसा", "paise", "पैसे", "hisaab", "हिसाब", "sab", "सब",
    "sabka", "सबका", "batao", "बताओ", "aaj", "kisko", "किसको", "entry", "एंट्री", "pichli", "पिछली"
} | {w for w in YES + NO + UDHAAR + JAMA if " " not in w}
NAME_AFTER = {"ko", "को", "ne", "ने", "ka", "का", "ki", "की", "ke", "के", "la", "ला", "ni", "नी", "chi", "ची", "से", "se"}


def parse_name(text: str) -> str | None:
    """The customer is the word before ko/ne/ka ("Ramesh ko ...", "सुरेश ने ..."), or a Marathi "-ला" suffix."""
    raw = TOKEN.findall(text)
    toks = tokens(text)
    for i, tok in enumerate(toks[1:], start=1):
        if tok in NAME_AFTER and toks[i - 1] not in STOP and not re.fullmatch(r"[\d.]+", toks[i - 1]):
            j = i - 1
            name = raw[j]
            # two-word names: "Ramesh doodhwala ko", "रमेश दूधवाले को"
            if j > 0 and toks[j - 1] not in STOP and not re.fullmatch(r"[\d.]+", toks[j - 1]) and j - 1 == 0:
                name = f"{raw[j - 1]} {name}"
            return name.strip(" ,.")
    has_money_talk = parse_amount(text) is not None or _has(text, UDHAAR + JAMA)
    for i, tok in enumerate(toks):
        m = re.fullmatch(r"([ऀ-ॿ]{2,})ला|([a-z]{3,})la", tok)
        if re.search(r"(wala|vala|वाला|वाले|wali|वाली)$", tok) or not has_money_talk:
            continue  # "doodhwala" is a nickname, not Marathi "Ramesh-la"
        if m and tok not in STOP and i < 3:
            return (m.group(1) or raw[i][:-2]).strip()
    return None


# --- dates -------------------------------------------------------------------------------

WEEKDAYS = {
    0: ["monday", "somvar", "सोमवार", "सोमवारी"], 1: ["tuesday", "mangalvar", "मंगलवार", "मंगळवारी"],
    2: ["wednesday", "budhvar", "बुधवार", "बुधवारी"], 3: ["thursday", "guruvar", "गुरुवार", "गुरुवारी"],
    4: ["friday", "shukravar", "शुक्रवार", "शुक्रवारी"], 5: ["saturday", "shanivar", "शनिवार", "शनिवारी"],
    6: ["sunday", "ravivar", "इतवार", "रविवार", "रविवारी", "itvar"],
}


def parse_due(text: str, today: date | None = None) -> str | None:
    today = today or date.today()
    low = text.lower()
    for wd, words in WEEKDAYS.items():
        if any(w in low for w in words):
            days = (wd - today.weekday()) % 7 or 7
            return (today + timedelta(days=days)).isoformat()
    if any(w in low for w in ["parso", "परसों"]):
        return (today + timedelta(days=2)).isoformat()
    if re.search(r"\b(kal|tomorrow)\b|कल|उद्या", low) and any(w in low for w in ["tak", "तक", "dega", "देगा", "degi", "देगी", "dene", "पर्यंत"]):
        return (today + timedelta(days=1)).isoformat()
    if any(w in low for w in ["agle hafte", "अगले हफ्ते", "next week", "ek hafte", "एक हफ्ते"]):
        return (today + timedelta(days=7)).isoformat()
    if any(w in low for w in ["mahine ke end", "month end", "महीने के अंत", "महीने के आखिर", "mahine ke aakhir"]):
        nxt = (today.replace(day=28) + timedelta(days=4))
        return (nxt - timedelta(days=nxt.day)).isoformat()
    m = re.search(r"(\d{1,2})\s*(?:tarikh|तारीख|tareekh|तारीख़)", low)
    if m:
        d = int(m.group(1))
        y, mo = today.year, today.month
        if d <= today.day:
            mo, y = (1, y + 1) if mo == 12 else (mo + 1, y)
        try:
            return date(y, mo, d).isoformat()
        except ValueError:
            return None
    return None


# --- items -------------------------------------------------------------------------------

CATALOG = ["aata", "chawal", "daal", "cheeni", "chai patti", "tel", "doodh", "dahi", "paneer", "ghee", "namak",
           "masala", "haldi", "mirch", "besan", "maida", "sooji", "poha", "biscuit", "chips", "maggi", "namkeen",
           "bread", "anda", "sabun", "surf", "shampoo", "toothpaste", "agarbatti", "matchbox", "cold drink",
           "pani bottle", "cigarette", "gutka", "kurkure", "chocolate", "rusk", "atta", "sugar", "rice", "oil", "milk"]
CATALOG_HI = {"आटा": "aata", "चावल": "chawal", "दाल": "daal", "चीनी": "cheeni", "शक्कर": "cheeni", "तेल": "tel",
              "दूध": "doodh", "दही": "dahi", "घी": "ghee", "नमक": "namak", "बिस्कुट": "biscuit", "चिप्स": "chips",
              "मैगी": "maggi", "साबुन": "sabun", "अंडा": "anda", "अंडे": "anda", "ब्रेड": "bread", "चाय": "chai patti",
              "पोहा": "poha", "बेसन": "besan", "मैदा": "maida", "नमकीन": "namkeen"}


def match_item(word: str) -> tuple[str, bool] | None:
    """Returns (catalog item, corrected?) for a heard word, e.g. "chicks" -> ("chips", True)."""
    w = word.lower()
    if w in CATALOG_HI:
        return CATALOG_HI[w], False
    if w in CATALOG:
        return w, False
    if len(w) < 4 or w in STOP or not re.fullmatch(r"[a-z]+", w):
        return None
    close = difflib.get_close_matches(w, CATALOG, n=1, cutoff=0.72)
    return (close[0], True) if close else None


def parse_items(text: str) -> tuple[str | None, list[str]]:
    """Returns ("aata 5 kilo, chips 2 packet", ["chicks -> chips"])."""
    raw = TOKEN.findall(text)
    toks = tokens(text)
    items, fixes, i = [], [], 0
    while i < len(toks):
        hit = match_item(toks[i]) if not re.fullmatch(r"[\d.,₹ ]+", toks[i]) else None
        if hit:
            name, fixed = hit
            if fixed:
                fixes.append(f"{raw[i]} -> {name}")
            qty = ""
            for k in (i + 1, i - 2):  # "aata 5 kilo" or "5 kilo aata"
                if 0 <= k < len(toks) - 1 and _word_value(toks[k]) is not None and toks[k + 1] in QTY_UNITS:
                    n = _word_value(toks[k])
                    qty = f" {int(n) if n == int(n) else n} {toks[k + 1]}"  # "पाँच किलो" -> "5 किलो"
                    break
            if name not in [x.split(" ")[0] for x in items]:
                items.append(name + qty)
        i += 1
    return (", ".join(items) or None), fixes


# --- whole utterance ---------------------------------------------------------------------

def understand(text: str, has_draft: bool = False, today: date | None = None) -> dict:
    """Best-effort parse of one utterance into an intent plus fields. Never raises."""
    amount = parse_amount(text)
    name = parse_name(text)
    entry_type = "jama" if _has(text, JAMA) else ("udhaar" if _has(text, UDHAAR) else None)
    items, fixes = parse_items(text)
    due = parse_due(text, today)

    if has_draft and is_yes(text):
        intent = "confirm"
    elif has_draft and is_no(text) and (amount or name or entry_type) :
        intent = "correct"
    elif has_draft and is_no(text):
        intent = "cancel"
    elif _has(text, UNDO):
        intent = "undo"
    elif _has(text, REMIND):
        intent = "reminders"
    elif _has(text, CUSTOMER_QUERY) and name and not amount:
        intent = "customer_query"
    elif _has(text, DUES) and not amount:
        intent = "dues_query"
    elif has_draft and (amount or entry_type or due or items) and not name:
        intent = "correct"
    elif amount or entry_type or name:
        intent = "entry"
    else:
        intent = "unclear"
    return {"intent": intent, "customer_name": name, "entry_type": entry_type, "amount_rupees": amount,
            "items": items, "item_fixes": fixes, "due_date": due}


def script_language(text: str) -> str:
    """Guess the reply language from typed text: Marathi, Hindi (Devanagari or Roman Hinglish) or English."""
    if re.search(r"[ऀ-ॿ]", text):
        end = r"(?=[\s,।.?!]|$)"  # Devanagari matras break \b, so mark word ends by hand
        marathi = (rf"(आहे|नको|दिले|झाले|पर्यंत|उद्या|अडीच|लिहू|बरोबर|नाही{end}|[ऀ-ॿ]+शे{end}|"
                   rf"[ऀ-ॿ]{{2,}}ला{end})")
        # "-ला" alone is also Hindi ("मिला", "दिला"), so it only counts next to money talk
        m = re.search(marathi, text)
        if m and (not m.group(0).endswith("ला") or parse_amount(text) or _has(text, UDHAAR + JAMA)):
            return "mr-IN"
        return "hi-IN"
    low = f" {text.lower()} "
    hinglish = ["ko", "ne", "ka", "ki", "hai", "udhaar", "udhar", "jama", "sau", "hazaar", "haan", "nahi", "tak",
                "dega", "kis", "baaki", "hisaab", "rameshla", "lihu"]
    if any(f" {w} " in low for w in hinglish) or re.search(r"[a-z]+la\b", low):
        return "hi-IN" if not re.search(r"\b\w+la\b|\bshe\b|lihu", low) else "mr-IN"
    return "en-IN"
