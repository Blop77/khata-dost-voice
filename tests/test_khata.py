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
    ("sawa sau", 125), ("sava do sau", 225), ("pachpan rupaye", 55), ("barah sau", 1200), ("paune do sau", 175), ("saadhe teen sau", 350), ("do hazaar paanch sau", 2500),
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


@pytest.mark.parametrize("answer,name", [("दूधवाला", "Ramesh doodhwala"), ("doodhwala", "Ramesh doodhwala"),
                                         ("pehla", "Ramesh"), ("dusra", "Ramesh doodhwala")])
def test_which_customer_answers(answer, name):
    say("Rmesh ko 50 ka udhaar")
    assert say(answer)["draft"]["name"] == name


@pytest.mark.parametrize("text,lang", [("आज किसको याद दिलाना है?", "hi-IN"), ("मुझे पैसे मिला", "hi-IN"),
                                       ("गणेशला तीनशे उधार दिले", "mr-IN"), ("रमेशला अडीचशे उधार", "mr-IN")])
def test_hindi_vs_marathi(text, lang):
    assert parser.script_language(text) == lang


# --- red-team regressions -----------------------------------------------------------------

def test_yes_with_a_change_corrects_instead_of_saving():
    say("Ramesh ko dhai sau ka udhaar")
    r = say("haan, 400 likho")
    assert not r.get("saved") and r["draft"]["amount"] == 400 and r["awaiting"] == "confirm"
    assert r["lang"] == "hi-IN"


def test_chatter_is_not_a_yes():
    say("Ramesh ko dhai sau ka udhaar")
    assert not say("ho gaya").get("saved")


def test_name_correction_keeps_amount():
    say("Ramesh ko 300 ka udhaar")
    r = say("nahi nahi, Suresh")
    assert r["draft"]["name"] == "Suresh" and r["draft"]["amount"] == 300


def test_similar_but_different_name_asks():
    r = say("Sunil ko 100 udhaar")
    assert r["awaiting"] == "which_customer" and "Sunita" in r["reply"] and "Sunil" in r["reply"]
    r = say("naya")
    assert r["draft"]["name"] == "Sunil" and r["draft"].get("new_customer")


def test_two_entries_in_one_breath_are_not_silently_dropped():
    r = say("Ramesh ko 200 udhaar aur Sunita ko 100 udhaar")
    assert "एक-एक" in r["reply"] and r["draft"] is None


@pytest.mark.parametrize("text,name,etype,amount", [
    ("Ramesh bhai ko 200 udhaar", "Ramesh", "udhaar", 200),
    ("Ramesh ji ne 200 de diye", "Ramesh", "jama", 200),
    ("Ramesh 200 udhaar", "Ramesh", "udhaar", 200),
    ("Ramesh ko 25 tarikh tak 300 udhaar", "Ramesh", "udhaar", 300),
    ("Sunita ne 800 mein se 300 diye", "Sunita", "jama", 300),
    ("Ramesh ka udhaar 300 kam karo", "Ramesh", "jama", 300),
    ("Ramesh ko 200 udhaar diye", "Ramesh", "udhaar", 200),
    ("सुरेशला दीड हजार उधार", "सुरेश", "udhaar", 1500),
    ("रमेशला साडेतीनशे उधार", "रमेश", "udhaar", 350),
    ("गणेशने पाचशे रुपये दिले", "गणेश", "jama", 500),
    ("Ramesh ko teen so udhaar", "Ramesh", "udhaar", 300),
])
def test_counter_phrasings(text, name, etype, amount):
    r = parser.understand(text)
    assert (r["customer_name"], r["entry_type"], r["amount_rupees"]) == (name, etype, amount)


def test_due_date_phrases():
    assert parser.parse_due("das din mein dega", FRI) == "2026-12-07"
    assert parser.parse_due("Sunday tak, Monday nahi", FRI) == "2026-11-29"


def test_switch_name_while_confirming_new_customer():
    say("Ramesh bhaiya ko 300 ka udhaar")  # bhaiya is dropped -> existing Ramesh, no new-customer question
    say("Vikram ko 300 ka udhaar")
    r = say("nahi nahi, Ganesh")
    assert r["draft"]["name"] == "Ganesh" and r["draft"]["amount"] == 300 and r["awaiting"] == "confirm"


def test_clean_name():
    from app.khata import clean_name
    assert clean_name("Ramesh bhai") == "Ramesh" and clean_name("Sunita ji") == "Sunita"


# --- English screen language ---------------------------------------------------------------

def test_english_mode_conversation():
    khata.prefer_language("en", "en-IN")
    r = say("Ramesh, 250 rupees credit, atta 5 kilo, pay by Monday", sid="en")
    assert r["lang"] == "en-IN" and r["draft"]["amount"] == 250 and "Shall I save it" in r["reply"]
    assert say("yes", sid="en")["saved"]["balance"] == 750


@pytest.mark.parametrize("text,intent,name", [("Who owes me money?", "dues_query", None),
                                              ("Who should I remind today?", "reminders", None),
                                              ("How much does Ramesh owe?", "customer_query", "Ramesh"),
                                              ("Give Priya 120 rupees credit", "entry", "Priya"),
                                              ("Sunita paid 400", "entry", "Sunita")])
def test_english_phrases(text, intent, name):
    r = parser.understand(text)
    assert r["intent"] == intent and r["customer_name"] == name


def test_screen_language_only_sets_the_start():
    khata.prefer_language("mix", "en-IN")
    assert say("रमेश को ढाई सौ का उधार", sid="mix")["lang"] == "hi-IN"  # speaking Hindi still gets Hindi


def test_stt_sends_bare_content_type(monkeypatch):
    """Chrome records 'audio/webm;codecs=opus'; Sarvam rejects the codecs suffix (seen live on 27 Nov)."""
    from app import speech
    sent = {}

    class FakeResp:
        def raise_for_status(self): pass
        def json(self): return {"transcript": "रमेश को 250 का उधार", "language_code": "hi-IN"}

    class FakeClient:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def post(self, url, headers=None, files=None, data=None):
            sent["type"] = files["file"][2]
            return FakeResp()

    monkeypatch.setenv("SARVAM_API_KEY", "test")
    monkeypatch.setattr(speech.httpx, "AsyncClient", FakeClient)
    asyncio.run(speech.transcribe(b"x" * 2000, "speech.webm", "audio/webm;codecs=opus"))
    assert sent["type"] == "audio/webm"


# --- period totals ---------------------------------------------------------------------

@pytest.mark.parametrize("text,period,focus", [
    ("How much money did I receive this month?", "month", "jama"),
    ("is mahine kitna jama hua", "month", "jama"),
    ("आज कितना पैसा मिला?", "today", "jama"),
    ("इस हफ्ते कितना उधार दिया", "week", "udhaar"),
    ("How much credit did I give today?", "today", "udhaar"),
    ("या महिन्यात किती पैसे मिळाले", "month", "jama"),
])
def test_summary_questions(text, period, focus):
    r = parser.understand(text)
    assert (r["intent"], r.get("period"), r["entry_type"]) == ("summary_query", period, focus)


def test_summary_answer_uses_ledger_numbers():
    say("Sunita ne 300 jama kiya", "haan", sid="s")
    r = say("is mahine kitna jama hua", sid="s")
    tot = ledger.totals("month")
    assert r["view"] == "summary" and str(tot["jama"]) in r["reply"].replace(",", "")


def test_dues_questions_are_not_summaries():
    assert parser.understand("kitna baaki hai")["intent"] == "dues_query"
    assert parser.understand("Total kitna udhaar hai")["intent"] == "dues_query"
    assert parser.understand("Ramesh ka kitna baaki hai")["intent"] == "customer_query"


@pytest.mark.parametrize("text", ["is mahine kitna jama hua", "aaj kitna paisa mila", "maine kitna udhaar diya"])
def test_roman_hinglish_is_hindi(text):
    assert parser.script_language(text) == "hi-IN"


def test_hindi_full_stop_from_speech_to_text():
    """Sarvam ends Hindi sentences with '।'. A spoken 'हाँ।' must still confirm (found while rehearsing the video)."""
    say("रमेश को ढाई सौ का उधार।")
    assert say("हाँ।").get("saved")
    say("सुनीता ने तीन सौ जमा किया।")
    assert say("नहीं, चार सौ।")["draft"]["amount"] == 400


def test_hindi_words_ending_in_ne_are_not_marathi_names():
    assert parser.understand("इस महीने कितना जमा हुआ?")["intent"] == "summary_query"
