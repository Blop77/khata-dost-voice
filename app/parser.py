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
# Hindi 11-99 are irregular words, so list them all (common Roman spellings + Devanagari).
_HINDI_11_99 = """gyarah ग्यारह 11|barah बारह 12|terah तेरह 13|chaudah चौदह 14|pandrah पंद्रह 15|solah सोलह 16|satrah सत्रह 17|
atharah अठारह 18|unnis उन्नीस 19|ikkis इक्कीस 21|bais बाईस 22|teis तेईस 23|chaubis चौबीस 24|pachis पच्चीस 25|chhabbis छब्बीस 26|
sattais सत्ताईस 27|atthais अट्ठाईस 28|untis उनतीस 29|iktis इकतीस 31|battis बत्तीस 32|taintis तैंतीस 33|chautis चौंतीस 34|
paintis पैंतीस 35|chhattis छत्तीस 36|saintis सैंतीस 37|adtis अड़तीस 38|untalis उनतालीस 39|iktalis इकतालीस 41|bayalis बयालीस 42|
taintalis तैंतालीस 43|chavalis चवालीस 44|paintalis पैंतालीस 45|chhiyalis छियालीस 46|saintalis सैंतालीस 47|adtalis अड़तालीस 48|
unchas उनचास 49|ikyavan इक्यावन 51|bavan बावन 52|tirpan तिरपन 53|chauvan चौवन 54|pachpan पचपन 55|chhappan छप्पन 56|
sattavan सत्तावन 57|atthavan अट्ठावन 58|unsath उनसठ 59|iksath इकसठ 61|basath बासठ 62|tirsath तिरसठ 63|chausath चौंसठ 64|
painsath पैंसठ 65|chhiyasath छियासठ 66|sadsath सड़सठ 67|adsath अड़सठ 68|unhattar उनहत्तर 69|ikhattar इकहत्तर 71|bahattar बहत्तर 72|
tihattar तिहत्तर 73|chauhattar चौहत्तर 74|pachhattar पचहत्तर 75|chhihattar छिहत्तर 76|sathattar सतहत्तर 77|athhattar अठहत्तर 78|
unasi उन्यासी 79|ikyasi इक्यासी 81|bayasi बयासी 82|tirasi तिरासी 83|chaurasi चौरासी 84|pachasi पचासी 85|chhiyasi छियासी 86|
sattasi सत्तासी 87|atthasi अट्ठासी 88|navasi नवासी 89|ikyanve इक्यानवे 91|banve बानवे 92|tiranve तिरानवे 93|chauranve चौरानवे 94|
pachanve पचानवे 95|chhiyanve छियानवे 96|sattanve सत्तानवे 97|atthanve अट्ठानवे 98|ninyanve निन्यानवे 99"""
for _row in _HINDI_11_99.replace("\n", "").split("|"):
    _roman, _deva, _n = _row.split()
    UNITS.setdefault(_roman, int(_n))
    UNITS.setdefault(_deva, int(_n))
UNITS.update({"baarah": 12, "bara": 12, "pandra": 15, "pacchis": 25, "pachees": 25, "pachchees": 25, "pachpan": 55,
              "sattar": 70, "nabbe": 90, "pachattar": 75, "pachahattar": 75, "aadha": 0.5, "आधा": 0.5})

SCALES = {"sau": 100, "सौ": 100, "hazaar": 1000, "hazar": 1000, "hajar": 1000, "हज़ार": 1000, "हजार": 1000,
          "lakh": 100000, "लाख": 100000, "hundred": 100, "thousand": 1000}
# "dhai sau" = 250, "dedh hazaar" = 1500, "sawa sau" = 125, "paune do sau" = 175, "saadhe teen sau" = 350
FRACTIONS = {"dhai": 2.5, "dhaai": 2.5, "ढाई": 2.5, "dedh": 1.5, "derh": 1.5, "डेढ़": 1.5, "डेढ": 1.5,
             "sawa": 1.25, "sava": 1.25, "सवा": 1.25, "adeech": 2.5, "अडीच": 2.5,
             "deed": 1.5, "did": 1.5, "दीड": 1.5}
MODIFIERS = {"saadhe": 0.5, "sadhe": 0.5, "साढ़े": 0.5, "साढे": 0.5, "साडे": 0.5, "paune": -0.25, "पौने": -0.25}
NOT_MONEY_AFTER = {"tarikh", "tareekh", "तारीख", "तारीख़", "din", "दिन", "mahine", "महीने", "hafte", "हफ्ते", "baje", "बजे",
                   "saal", "साल", "minute", "मिनट", "ghante", "घंटे"}
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
            nxt_tok = toks[i + 1] if i + 1 < len(toks) else ""
            if tok in ("sawa", "sava", "सवा") and _word_value(nxt_tok) is not None:
                mod = 0.25  # "sawa do sau" = 225, but "sawa sau" = 125
            elif tok in FRACTIONS:
                frac = FRACTIONS[tok]
            elif tok in MODIFIERS:
                mod = MODIFIERS[tok]
            elif _word_value(tok) is not None:
                if current and (re.fullmatch(r"[\d.]+", tok) or re.fullmatch(r"[\d.]+", toks[i - 1])):
                    break  # two separate numbers: "250 5", or "100, das din" (a numeral is complete on its own)
                current += _word_value(tok)
            elif tok in SCALES:
                base = frac if frac is not None else (current + mod if current else (1 + mod if mod else 1))
                if SCALES[tok] == 100:
                    current = base * 100
                else:
                    total += base * SCALES[tok]
                    current = 0.0
                frac, mod = None, 0.0
            elif tok == "so" and current:  # speech-to-text often writes "teen sau" as "teen so"
                current *= 100
            elif she and _marathi_hundreds(she.group(1)) is not None:
                current = _marathi_hundreds(she.group(1)) * 100
            else:
                break
            used = True
            i += 1
        if used:
            value = total + current
            if value > 0:
                nxt = toks[i] if i < len(toks) else ""
                prev = toks[start - 1] if start > 0 else ""
                is_qty = nxt in QTY_UNITS or nxt in NOT_MONEY_AFTER
                money = (not is_qty) and (nxt in MONEY_MARKERS or prev in MONEY_MARKERS or value >= 10
                                          or any(t in SCALES or t in FRACTIONS for t in toks[start:i]))
                found.append({"value": int(round(value)), "start": start, "money": money, "qty": is_qty})
        else:
            i += 1
    return found


def _marathi_hundreds(head: str) -> float | None:
    """"अडीच" -> 2.5, "पाच" -> 5, "साडेतीन" -> 3.5 (as in अडीचशे, पाचशे, साडेतीनशे)."""
    extra = {"पाच": 5, "पंधरा": 15, "तीन": 3, "चार": 4, "सहा": 6, "आठ": 8, "नऊ": 9, "दहा": 10, "दोन": 2, "एक": 1, "सात": 7}
    if head.startswith("साडे"):
        rest = _marathi_hundreds(head[4:])
        return rest + 0.5 if rest is not None else None
    return FRACTIONS.get(head) or UNITS.get(head) or extra.get(head)


def parse_amount(text: str) -> int | None:
    # "800 mein se 300 diye": the payment is what comes after "mein se"
    m = re.search(r"(mein se|में से|me se|madhun|मधून)\s", text.lower())
    if m:
        after = [a for a in find_amounts(text[m.end():]) if a["money"]]
        if after:
            return after[0]["value"]
    money = [a for a in find_amounts(text) if a["money"]]
    return money[0]["value"] if money else None


# --- intent words ------------------------------------------------------------------------

def _has(text: str, words) -> bool:
    low = " " + re.sub(r"[,.!?।;:\"'()\-]+", " ", text.lower()) + " "  # "haan, 400" -> " haan 400 "
    low = re.sub(r"\s+", " ", low)
    return any(f" {w} " in low or (len(w) > 3 and w in low) for w in words)


UDHAAR = ["udhaar", "udhar", "udhari", "उधार", "उधारी", "credit", "baaki likh", "likh lo", "khate me", "khate mein",
          "खाते में", "le gaya", "le gayi", "ले गया", "ले गई", "दिया उधार", "baad mein dega", "baad me dega", "बाद में देगा",
          "baad mein degi", "बाद में देगी", "baad mein de dega", "नेले", "नेला"]
# Explicit payment words win over everything.
JAMA = ["jama", "जमा", "paid", "payment", "लौटाए", "lautaye", "chukaya", "चुकाया", "wapas", "वापस", "mile", "मिले",
        "bhar diya", "भर दिया", "kam karo", "कम करो", "ghatao", "घटाओ", "kam kar do", "कम कर दो", "परत", "भरले"]
# Verbs whose meaning depends on direction: "Ramesh NE 200 diye" = paid you; "Ramesh KO 200 diye" = you gave credit.
GAVE = ["de gaya", "de gayi", "दे गया", "दे गई", "diye", "दिए", "de diye", "दे दिए", "diya", "दिया", "दिले", "dile"]
TO_CUSTOMER = {"ko", "को", "la", "ला"}
FROM_CUSTOMER = {"ne", "ने"}


def entry_type(text: str) -> str | None:
    if _has(text, JAMA):
        if _has(text, ["udhaar nahi", "उधार नहीं"]) or not re.search(r"(jama|जमा)\s*(nahi|नहीं)", text.lower()):
            return "jama"
        return "udhaar"  # "jama nahi, udhaar"
    if _has(text, UDHAAR):
        return "udhaar"
    if _has(text, GAVE):
        toks = tokens(text)
        if any(t in FROM_CUSTOMER or re.fullmatch(r"[ऀ-ॿ]{2,}ने", t) for t in toks):
            return "jama"
        if any(t in TO_CUSTOMER or re.fullmatch(r"[ऀ-ॿ]{2,}ला", t) for t in toks):
            return "udhaar"
        return "jama"
    return None
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


YES_WORDS = {"haan", "han", "ha", "haa", "haanji", "हाँ", "हां", "हा", "ok", "okay", "ओके", "theek", "thik", "ठीक", "hai", "है",
             "sahi", "सही", "likh", "likho", "लिख", "लिखो", "do", "दो", "lo", "लो", "yes", "ji", "जी", "बरोबर", "barobar",
             "save", "karo", "करो", "kar", "कर", "bilkul", "बिल्कुल", "haanji", "lihi", "लिहा", "हो", "chalega", "चलेगा"}


def is_yes(text: str) -> bool:
    """Strict: EVERY word must be a yes-word. "haan, 400" or "haan Sunita ka" is a correction, never a save.
    A lone Marathi "हो" counts; Hinglish "ho gaya" does not."""
    toks = tokens(text)
    if not toks or len(toks) > 4 or _has(text, NO):
        return False
    if toks == ["ho"]:
        return False
    return all(t in YES_WORDS for t in toks) and any(t not in {"hai", "है", "do", "दो", "lo", "लो", "karo", "करो", "kar", "कर", "ji", "जी"} for t in toks)


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


HONORIFIC = {"bhai", "भाई", "bhaiya", "भैया", "ji", "जी", "didi", "दीदी", "seth", "सेठ", "sahab", "साहब", "saab", "aunty",
             "आंटी", "uncle", "अंकल", "chacha", "चाचा", "kaka", "काका", "tai", "ताई", "mausi", "मौसी", "bhabhi", "भाभी",
             "dada", "दादा", "anna", "अण्णा", "madam", "मैडम"}


def _is_word(tok: str) -> bool:
    return tok not in STOP and tok not in HONORIFIC and not re.fullmatch(r"[\d.]+", tok) and len(tok) > 1


def parse_name(text: str, has_draft: bool = False) -> str | None:
    """The customer is the word before ko/ne/ka ("Ramesh ko ...", "सुरेश ने ..."), skipping honorifics
    ("Ramesh bhai ko"), or a Marathi "-ला"/"-ने" suffix, or a bare leading name ("Ramesh 200 udhaar")."""
    raw = TOKEN.findall(text)
    toks = tokens(text)
    for i, tok in enumerate(toks[1:], start=1):
        if tok in NAME_AFTER:
            j = i - 1
            while j >= 0 and toks[j] in HONORIFIC:
                j -= 1
            if j >= 0 and _is_word(toks[j]):
                name = raw[j]
                # two-word names at the start: "Ramesh doodhwala ko", "रमेश दूधवाले को"
                if j == 1 and _is_word(toks[0]):
                    name = f"{raw[0]} {name}"
                return name.strip(" ,.")
    money_talk = parse_amount(text) is not None or entry_type(text) is not None
    for i, tok in enumerate(toks[:3]):
        if re.search(r"(wala|vala|वाला|वाले|wali|वाली)$", tok) or not money_talk:
            continue  # "doodhwala" is a nickname, not Marathi "Ramesh-la"
        m = re.fullmatch(r"([ऀ-ॿ]{2,})(?:ला|ने|नी)|([a-z]{3,})la", tok)
        if m and tok not in STOP:
            return (m.group(1) or raw[i][:-2]).strip()
    # A bare name: "Ramesh 200 udhaar", or a correction "nahi nahi, Suresh"
    content = [(raw[i], t) for i, t in enumerate(toks) if t not in NO and t not in HONORIFIC]
    if content and (money_talk or (has_draft and _has(text, NO))):
        word, tok = content[0]
        if _is_word(tok) and not match_item(tok) and (word[:1].isupper() or re.match(r"[ऀ-ॿ]", word)
                                                       or (has_draft and len(content) == 1)):
            return word.strip(" ,.")
    return None


def count_entries(text: str) -> int:
    """How many separate customer entries are in one sentence ("Ramesh ko 200 aur Sunita ko 100")."""
    parts = re.split(r"\s(?:aur|और|ani|आणि|and|,)\s", text)
    return sum(1 for p in parts if parse_amount(p) is not None and parse_name(p) is not None) or 1


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
    # the FIRST weekday mentioned wins: "Sunday tak, Monday nahi" -> Sunday
    hits = [(low.find(w), wd) for wd, words in WEEKDAYS.items() for w in words if w in low]
    if hits:
        wd = min(hits)[1]
        days = (wd - today.weekday()) % 7 or 7
        return (today + timedelta(days=days)).isoformat()
    m = re.search(r"(\S+)\s+(?:din|दिन|divas|दिवस)", low)  # "das din mein", "3 din mein"
    if m:
        n = _word_value(m.group(1).replace(",", ""))
        if n and 0 < n <= 365:
            return (today + timedelta(days=int(n))).isoformat()
    if any(w in low for w in ["agle mahine", "अगले महीने", "next month", "पुढच्या महिन्यात"]):
        y, mo = (today.year + 1, 1) if today.month == 12 else (today.year, today.month + 1)
        try:
            return date(y, mo, today.day).isoformat()
        except ValueError:
            return date(y, mo, 28).isoformat()
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
    name = parse_name(text, has_draft=has_draft)
    etype = entry_type(text)
    items, fixes = parse_items(text)
    due = parse_due(text, today)
    if count_entries(text) > 1:
        return {"intent": "multiple", "customer_name": name, "entry_type": etype, "amount_rupees": amount,
                "items": items, "item_fixes": fixes, "due_date": due}

    if has_draft and is_yes(text):
        intent = "confirm"
    elif has_draft and is_no(text) and (amount or name or etype):
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
    elif has_draft and (amount or etype or due or items) and not name:
        intent = "correct"
    elif has_draft and _has(text, YES) and (amount or name or etype):
        intent = "correct"  # "haan, 400" / "haan Sunita ka": a yes that changes something is a correction
    elif amount or etype or name:
        intent = "entry"
    else:
        intent = "unclear"
    return {"intent": intent, "customer_name": name, "entry_type": etype, "amount_rupees": amount,
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
    low = " " + re.sub(r"\s+", " ", re.sub(r"[,.!?।;:\"'()\-]+", " ", text.lower())) + " "
    hinglish = ["ko", "ne", "ka", "ki", "hai", "udhaar", "udhar", "jama", "sau", "hazaar", "haan", "nahi", "tak",
                "dega", "kis", "baaki", "hisaab", "rameshla", "lihu", "likho", "likh", "theek", "rupaye", "diye"]
    if any(f" {w} " in low for w in hinglish) or re.search(r"[a-z]+la\b", low):
        return "hi-IN" if not re.search(r"\b\w+la\b|\bshe\b|lihu", low) else "mr-IN"
    return "en-IN"
