"""The khata itself: customers and udhaar/jama entries in SQLite. Balances are always computed from entries."""
import difflib
import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path

DB_PATH = Path(os.getenv("LEDGER_DB", Path(__file__).resolve().parent.parent / "data" / "khata.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  name_key TEXT NOT NULL,
  phone TEXT,
  language TEXT DEFAULT 'hi-IN',
  reminder_consent INTEGER DEFAULT 0,
  consent_at TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS entries (
  id INTEGER PRIMARY KEY,
  customer_id INTEGER NOT NULL REFERENCES customers(id),
  type TEXT NOT NULL CHECK (type IN ('udhaar', 'jama')),
  amount INTEGER NOT NULL CHECK (amount > 0),
  items TEXT,
  due_date TEXT,
  heard TEXT,
  created_at TEXT NOT NULL,
  deleted_at TEXT
);
"""

# --- names across scripts ----------------------------------------------------------------

_CONS = {"क": "k", "ख": "kh", "ग": "g", "घ": "gh", "च": "ch", "छ": "chh", "ज": "j", "झ": "jh", "ट": "t", "ठ": "th",
         "ड": "d", "ढ": "dh", "ण": "n", "त": "t", "थ": "th", "द": "d", "ध": "dh", "न": "n", "प": "p", "फ": "ph",
         "ब": "b", "भ": "bh", "म": "m", "य": "y", "र": "r", "ल": "l", "ळ": "l", "व": "v", "श": "sh", "ष": "sh",
         "स": "s", "ह": "h", "ड़": "r", "ढ़": "rh", "क़": "k", "ज़": "z", "फ़": "f"}
_VOW = {"अ": "a", "आ": "aa", "इ": "i", "ई": "ee", "उ": "u", "ऊ": "oo", "ए": "e", "ऐ": "ai", "ओ": "o", "औ": "au", "ऋ": "ri"}
_MATRA = {"ा": "aa", "ि": "i", "ी": "ee", "ु": "u", "ू": "oo", "े": "e", "ै": "ai", "ो": "o", "ौ": "au", "ृ": "ri",
          "ं": "n", "ँ": "n", "ः": "h"}


def to_latin(text: str) -> str:
    """Rough Devanagari -> Latin so that "रमेश" and "Ramesh" can be compared."""
    out, chars, i = [], list(text), 0
    while i < len(chars):
        c = chars[i]
        if c in _CONS:
            nxt = chars[i + 1] if i + 1 < len(chars) else ""
            out.append(_CONS[c])
            if nxt == "्":
                i += 1
            elif nxt not in _MATRA and nxt != "़":
                out.append("a")
        elif c in _VOW:
            out.append(_VOW[c])
        elif c in _MATRA:
            out.append(_MATRA[c])
        elif c not in "़्":
            out.append(c)
        i += 1
    word = "".join(out)
    return re.sub(r"a\b", "", word)  # schwa deletion at word end: "रमेश" -> "ramesh", not "ramesha"


def name_key(name: str) -> str:
    """Spelling-tolerant key: रमेश, Ramesh, Rmesh and Ramessh all map close together."""
    k = to_latin(name.strip().lower())
    for a, b in [("aa", "a"), ("ee", "i"), ("oo", "u"), ("sh", "s"), ("w", "v"), ("ph", "f"), ("z", "j"),
                 ("q", "k"), ("y", "i"), ("ck", "k")]:
        k = k.replace(a, b)
    k = re.sub(r"(.)\1+", r"\1", k)  # doubled letters
    k = re.sub(r"a\b", "", k)  # final "a" is silent or optional in both scripts: Sunita = सुनीता
    return re.sub(r"[^a-z ]", "", k).strip()


def _similar(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    # compare first names too, so "Ramesh" matches "Ramesh doodhwala"
    best = difflib.SequenceMatcher(None, a, b).ratio()
    for part in b.split():
        best = max(best, difflib.SequenceMatcher(None, a, part).ratio() - (0.05 if " " in b else 0))
    return best


# --- storage -----------------------------------------------------------------------------

@contextmanager
def db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def find_customers(name: str, threshold: float = 0.78) -> list[dict]:
    """Customers whose name sounds like `name`, best first."""
    key = name_key(name)
    with db() as conn:
        rows = [dict(r) for r in conn.execute("SELECT * FROM customers")]
    scored = sorted(((_similar(key, r["name_key"]), r) for r in rows), key=lambda x: -x[0])
    exact = [r for s, r in scored if r["name_key"] == key]
    if exact:
        return exact
    return [r for s, r in scored if s >= threshold]


def add_customer(name: str, language: str = "hi-IN", phone: str | None = None) -> dict:
    with db() as conn:
        cur = conn.execute("INSERT INTO customers (name, name_key, phone, language, created_at) VALUES (?,?,?,?,?)",
                           (name.strip(), name_key(name), phone, language, _now()))
        return dict(conn.execute("SELECT * FROM customers WHERE id=?", (cur.lastrowid,)).fetchone())


def update_customer(customer_id: int, **fields) -> dict | None:
    allowed = {k: v for k, v in fields.items() if k in {"phone", "language", "reminder_consent", "name"}}
    if "name" in allowed:
        allowed["name_key"] = name_key(allowed["name"])
    if "reminder_consent" in allowed:  # DPDP: keep when the customer said yes (or withdrew)
        allowed["reminder_consent"] = 1 if allowed["reminder_consent"] else 0
        allowed["consent_at"] = _now() if allowed["reminder_consent"] else None
    if "phone" in allowed and allowed["phone"]:
        digits = re.sub(r"\D", "", str(allowed["phone"]))
        allowed["phone"] = ("91" + digits) if len(digits) == 10 else digits
    with db() as conn:
        if allowed:
            sets = ", ".join(f"{k}=?" for k in allowed)
            conn.execute(f"UPDATE customers SET {sets} WHERE id=?", (*allowed.values(), customer_id))
        row = conn.execute("SELECT * FROM customers WHERE id=?", (customer_id,)).fetchone()
        return dict(row) if row else None


def add_entry(customer_id: int, type_: str, amount: int, items: str | None = None,
              due_date: str | None = None, heard: str | None = None) -> dict:
    if type_ not in ("udhaar", "jama") or int(amount) <= 0:
        raise ValueError("entry needs a type (udhaar/jama) and a positive amount")
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO entries (customer_id, type, amount, items, due_date, heard, created_at) VALUES (?,?,?,?,?,?,?)",
            (customer_id, type_, int(amount), items, due_date, heard, _now()))
        return dict(conn.execute("SELECT * FROM entries WHERE id=?", (cur.lastrowid,)).fetchone())


def undo_last() -> dict | None:
    """Soft-deletes the most recent entry (kept for audit) and returns it."""
    with db() as conn:
        row = conn.execute("SELECT e.*, c.name FROM entries e JOIN customers c ON c.id=e.customer_id "
                           "WHERE deleted_at IS NULL ORDER BY e.id DESC LIMIT 1").fetchone()
        if not row:
            return None
        conn.execute("UPDATE entries SET deleted_at=? WHERE id=?", (_now(), row["id"]))
        return dict(row)


def balance(customer_id: int) -> int:
    with db() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(CASE type WHEN 'udhaar' THEN amount ELSE -amount END), 0) AS bal "
            "FROM entries WHERE customer_id=? AND deleted_at IS NULL", (customer_id,)).fetchone()
        return int(row["bal"])


def customers_with_balance() -> list[dict]:
    """Every customer with their balance and the earliest open due date, most owed first."""
    with db() as conn:
        rows = conn.execute("""
            SELECT c.*,
              COALESCE(SUM(CASE e.type WHEN 'udhaar' THEN e.amount ELSE -e.amount END), 0) AS balance,
              MIN(CASE WHEN e.type='udhaar' THEN e.due_date END) AS due_date,
              MAX(e.created_at) AS last_activity
            FROM customers c LEFT JOIN entries e ON e.customer_id=c.id AND e.deleted_at IS NULL
            GROUP BY c.id ORDER BY balance DESC, c.name""").fetchall()
        return [dict(r) for r in rows]


def customer_detail(customer_id: int) -> dict | None:
    with db() as conn:
        c = conn.execute("SELECT * FROM customers WHERE id=?", (customer_id,)).fetchone()
        if not c:
            return None
        entries = [dict(r) for r in conn.execute(
            "SELECT * FROM entries WHERE customer_id=? AND deleted_at IS NULL ORDER BY id DESC", (customer_id,))]
    return {**dict(c), "balance": balance(customer_id), "entries": entries}


def recent_entries(limit: int = 20) -> list[dict]:
    with db() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT e.*, c.name FROM entries e JOIN customers c ON c.id=e.customer_id "
            "WHERE e.deleted_at IS NULL ORDER BY e.id DESC LIMIT ?", (limit,))]


def due_customers(on: date | None = None) -> list[dict]:
    """Customers who still owe money and whose promised date is today or past."""
    day = (on or date.today()).isoformat()
    return [c for c in customers_with_balance() if c["balance"] > 0 and c["due_date"] and c["due_date"] <= day]


def reset_demo() -> None:
    """Wipes the ledger and loads a few realistic customers so a demo starts from a known state."""
    with db() as conn:
        conn.executescript("DELETE FROM entries; DELETE FROM customers;")
    today = date.today()
    seed = [
        ("Ramesh", "hi-IN", "919800000001", [("udhaar", 500, "chawal 5 kilo", (today - timedelta(days=1)).isoformat())]),
        ("Sunita", "hi-IN", "919800000002", [("udhaar", 1200, "masala, tel", today.isoformat()),
                                             ("jama", 400, None, None)]),
        ("Ramesh doodhwala", "hi-IN", None, [("udhaar", 80, "biscuit", None)]),
        ("Ganesh", "mr-IN", "919800000003", [("udhaar", 300, "poha, cheeni", (today + timedelta(days=3)).isoformat())]),
    ]
    for name, lang, phone, entries in seed:
        c = add_customer(name, lang, phone)
        update_customer(c["id"], reminder_consent=1 if phone else 0)
        for t, amt, items, due in entries:
            add_entry(c["id"], t, amt, items, due, heard="(demo data)")
