"""Keyless tests: the rule parser and the conversation run with no API keys, exactly as `docker compose up` does."""
import asyncio
import os
from datetime import date

import pytest

os.environ["OPENAI_API_KEY"] = ""
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["LLM_PROVIDER"] = "openai"

from app import khata, ledger, parser  # noqa: E402

FRI = date(2026, 11, 27)


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(ledger, "DB_PATH", tmp_path / "khata.db")
    ledger.reset_demo()
    khata.SESSIONS.clear()


def say(*lines, sid="t"):
    out = None
    for line in lines:
        out = asyncio.run(khata.handle(sid, line))
    return out


# --- numbers and parsing -----------------------------------------------------------------

@pytest.mark.parametrize("text,amount", [
    ("Ramesh ko dhai sau ka udhaar", 250), ("रमेश को ढाई सौ का उधार", 250), ("dedh hazaar", 1500),
    ("sawa sau", 125), ("paune do sau", 175), ("saadhe teen sau", 350), ("do hazaar paanch sau", 2500),
    ("रमेशला अडीचशे उधार", 250), ("₹1,200 udhaar", 1200), ("aata 5 kilo, 60 rupaye", 60),
])
def test_amounts(text, amount):
    assert parser.parse_amount(text) == amount


def test_quantities_are_not_money():
    assert parser.parse_amount("aata 5 kilo aur 2 packet chips") is None


def test_full_sentence():
    r = parser.understand("Ramesh ko dhai sau ka udhaar, aata 5 kilo, Monday tak dega", today=FRI)
    assert r == {"intent": "entry", "customer_name": "Ramesh", "entry_type": "udhaar", "amount_rupees": 250,
                 "items": "aata 5 kilo", "item_fixes": [], "due_date": "2026-11-30"}


def test_misheard_item_is_corrected():
    r = parser.understand("Mohan ko 2 packet chicks, 40 rupaye udhaar")
    assert r["items"] == "chips 2 packet" and r["item_fixes"] == ["chicks -> chips"]


def test_names_across_scripts():
    assert ledger.name_key("रमेश") == ledger.name_key("Ramesh") == ledger.name_key("Ramessh")
    assert ledger.name_key("सुनीता") == ledger.name_key("Sunita")


# --- the conversation --------------------------------------------------------------------

def test_nothing_saved_until_yes():
    before = ledger.balance(ledger.find_customers("Ramesh")[0]["id"])
    r = say("Ramesh ko dhai sau ka udhaar")
    assert r["awaiting"] == "confirm" and "लिख दूँ" in r["reply"]
    assert ledger.balance(ledger.find_customers("Ramesh")[0]["id"]) == before
    r = say("haan")
    assert r["saved"]["balance"] == before + 250
    assert "250" in r["saved"]["receipt"]


def test_correction_changes_only_amount():
    say("Sunita ne 300 jama kiya")
    r = say("nahi, 400")
    assert r["draft"]["amount"] == 400 and r["draft"]["type"] == "jama"
    assert r["lang"] == "hi-IN"  # a short reply keeps the conversation language


def test_ambiguous_name_asks_which():
    r = say("Rmesh ko 50 ka udhaar")
    assert r["awaiting"] == "which_customer"
    r = say("doodhwala")
    assert r["draft"]["name"] == "Ramesh doodhwala" and r["awaiting"] == "confirm"


def test_new_customer_needs_confirmation_and_keeps_amount():
    r = say("Vijay ko udhaar")
    assert r["awaiting"] == "confirm_new_customer"
    say("saat hazaar do sau")
    r = say("haan")
    assert r["draft"]["amount"] == 7200 and "7 2 0 0" in r["reply"]  # big amounts are spelled out


def test_stale_readback_is_never_saved_by_a_stray_yes():
    say("Ramesh ko dhai sau ka udhaar")
    say("kis kis ka paisa baaki hai")
    r = say("haan")
    assert not r.get("saved") and r["awaiting"] == "confirm"  # read back again first
    assert say("haan").get("saved")


def test_undo_asks_first():
    say("Ramesh ko 100 ka udhaar", "haan")
    r = say("pichli entry hatao")
    assert r["awaiting"] == "undo_confirm"
    r = say("haan")
    assert r["undone"]["amount"] == 100


def test_dues_and_reminders():
    r = say("kis kis ka paisa baaki hai")
    assert r["view"] == "dues" and r["dues"][0]["balance"] >= r["dues"][-1]["balance"]
    reminders = khata.reminders()
    assert {x["name"] for x in reminders} == {"Ramesh", "Sunita"}
    assert all(x["consent"] for x in reminders)


def test_marathi():
    r = say("रमेशला अडीचशे उधार")
    assert r["lang"] == "mr-IN" and "लिहू का" in r["reply"]


def test_cancel():
    say("Ramesh ko 100 ka udhaar")
    r = say("नहीं")
    assert r["draft"] is None and r["awaiting"] is None


def test_new_name_starts_a_fresh_entry():
    say("Mohan ko 2 packet chips, 40 rupaye udhaar", "haan")  # confirm new customer -> read-back pending
    r = say("Ramesh ko 100 ka udhaar")
    assert r["draft"]["name"] == "Ramesh" and r["draft"]["amount"] == 100 and not r["draft"].get("items")


def test_english_owner_gets_english():
    r = say("Give Priya credit of 120 rupees")
    assert r["lang"] == "en-IN"
