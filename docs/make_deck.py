"""Builds docs/Khata_Dost_pitch.pdf. Judges read the words, so every slide is plain text.

Run:  python docs/make_deck.py   (needs `pip install reportlab`)
Fill the LINKS below before the final export.
"""
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (BaseDocTemplate, Frame, PageBreak, PageTemplate, Paragraph, Spacer, Table,
                                TableStyle)

LINKS = {
    "github": "https://github.com/Blop77/khata-dost-voice",
    "video": "[TODO: YouTube link]",
    "live": "[TODO: live link, if submitted]",
}
OUT = Path(__file__).resolve().parent / "Khata_Dost_pitch.pdf"
W, H = landscape((540, 960))  # 16:9
GREEN, RED, INK, MUTED = colors.HexColor("#14532d"), colors.HexColor("#b91c1c"), colors.HexColor("#1b1a17"), colors.HexColor("#5f5a50")

title = ParagraphStyle("t", fontName="Helvetica-Bold", fontSize=30, leading=36, textColor=GREEN, spaceAfter=14)
kicker = ParagraphStyle("k", fontName="Helvetica-Bold", fontSize=12, leading=16, textColor=MUTED, spaceAfter=4)
body = ParagraphStyle("b", fontName="Helvetica", fontSize=15.5, leading=22, textColor=INK, spaceAfter=8)
small = ParagraphStyle("s", parent=body, fontSize=11, leading=14, textColor=MUTED)
bullet = ParagraphStyle("bl", parent=body, leftIndent=18, bulletIndent=2)
big = ParagraphStyle("big", fontName="Helvetica-Bold", fontSize=40, leading=46, textColor=GREEN, spaceAfter=10)
cell = ParagraphStyle("c", fontName="Helvetica", fontSize=12, leading=15, textColor=INK)
cellb = ParagraphStyle("cb", parent=cell, fontName="Helvetica-Bold")


def bullets(items):
    return [Paragraph(t, bullet, bulletText="•") for t in items]


def table(rows, widths):
    data = [[Paragraph(str(c), cellb if i == 0 else cell) for c in r] for i, r in enumerate(rows)]
    t = Table(data, colWidths=widths, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e7f6ec")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d6d0c4")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 9)
    canvas.setFillColor(MUTED)
    canvas.drawString(40, 18, "Khata Dost  ·  India Runs on Voice, Round 2  ·  Livelihoods and small business")
    canvas.drawRightString(W - 40, 18, str(doc.page))
    canvas.restoreState()


S = []


def slide(kick, head, *flow):
    S.extend([Paragraph(kick, kicker), Paragraph(head, title), *flow, PageBreak()])


slide("KHATA DOST  ·  Bolo, khata likho",
      "A voice ledger for kirana udhaar",
      Paragraph("The shop owner says the entry out loud while serving. Khata Dost reads it back, saves it only after "
                "the owner says <b>haan</b>, keeps every balance, and prepares a receipt in the customer's own language.", body),
      Spacer(1, 10),
      Paragraph("<b>Theme:</b> Livelihoods and small business. Extends my Round 1 idea.", body),
      Paragraph(f"<b>Code:</b> {LINKS['github']}<br/><b>Demo video:</b> {LINKS['video']}<br/><b>Live link:</b> {LINKS['live']}", body),
      Paragraph("Built solo during the hackathon, dictated with Wispr Flow.", small))

slide("1 · THE PROBLEM", "Udhaar is how kiranas keep customers, and how they lose money",
      *bullets([
          "Kiranas run on informal credit. Redseer names <b>trusted credit</b> as a core reason households shop at kiranas, "
          "and a 2022 Flourish survey found about <b>1 in 3 customers</b> regularly buy on store credit.",
          "Today the owner writes udhaar in a paper bahi or keeps it in memory. In the evening rush, with both hands busy "
          "and a customer waiting, entries get skipped. At month end amounts are disputed and small dues quietly become lost money.",
          "<b>UPI records the money that is paid. Udhaar is the money that isn't</b>, so it never shows up in any payment log.",
          "Typing ledgers (Khatabook, OkCredit) need a free hand, a few screens and some reading; at the counter they are slower than paper.",
      ]))

slide("1 · THE SOLUTION", "The whole loop is spoken, start to finish",
      table([
          ["Owner says", "Khata Dost says / does"],
          ["\"Ramesh ko dhai sau ka udhaar, aata 5 kilo, Monday tak dega\"",
           "\"Ramesh, udhaar 250 rupaye, aata 5 kilo, Somvar 30 November tak. Likh doon?\" and shows a red UDHAAR card"],
          ["\"Haan\" (heard automatically, no second tap)",
           "Saves. \"Likh diya. Ramesh ka kul baaki 750.\" A receipt in the customer's language is ready to send in one tap"],
          ["\"Nahi, teen sau\"", "Changes only the amount and reads it back again"],
          ["\"Kis kis ka paisa baaki hai?\"", "Speaks the top five who owe most, total, full list on screen"],
          ["\"Aaj kisko yaad dilana hai?\"", "Lists who is due today with a polite WhatsApp message in each customer's language"],
          ["\"Pichli entry hatao\"", "Asks first, then removes the last entry (kept in an audit trail)"],
      ], [330, 520]),
      Spacer(1, 8),
      Paragraph("Works in Hindi, Hinglish, basic Marathi and English today. One tap per entry; about 2 to 3 seconds from "
                "the end of speech to the spoken reply in my tests with Sarvam and OpenAI keys.", body))

slide("1 · WHY YOU CAN TRUST IT", "A ledger is money: the design is built around not getting amounts wrong",
      *bullets([
          "<b>Nothing is saved until the owner hears it and says yes.</b> A stray \"haan\" after another question never saves an old draft.",
          "<b>The AI never speaks a number.</b> It only extracts the entry; balances and spoken amounts come from the database.",
          "<b>Two independent readers.</b> A rule parser (dhai sau = 250, dedh hazaar = 1500, Marathi adeechshe = 250) checks the AI "
          "(with no AI key, the rules work alone). "
          "If they disagree, the app asks: \"7 ya 60? Phir se boliye.\"",
          "<b>Big amounts are read digit by digit</b> (\"7200, yaani 7 2 0 0\"), because a misheard zero costs real money.",
          "<b>Names across scripts and spellings</b> (Ramesh in Devanagari = Ramesh = Rmesh); two Rameshes? It asks \"Kaun se? Ramesh, Ramesh doodhwala\".",
          "<b>Misheard items are corrected</b> against a kirana catalogue (\"chicks packet\" becomes chips) and shown on screen.",
          "<b>Still works with no AI key:</b> the rule parser and the phone's own voice keep the core loop running.",
      ]))

slide("2 · WHO IT IS FOR", "Owners first, their customers second",
      Paragraph("1.2 to 1.4 crore", big),
      Paragraph("kirana stores in India (Ministry of Commerce, Jun 2026: \"over 1.4 crore\"; distributor federation: about 1.3 crore). "
                "Kiranas hold about 91% of a $658B grocery market (Redseer 2026).", body),
      *bullets([
          "<b>Primary user:</b> owner, 25 to 60, speaks Hindi, Hinglish or a regional language, more comfortable talking than typing.",
          "<b>They are already on phones:</b> 94% of small merchants accept UPI (DFS survey, 2025); 71% of small retailers use a "
          "smartphone as their main business device (PayNearby 2025). But only about 1 in 10 kiranas is digitised beyond payments.",
          "<b>Secondary user:</b> the customer, who gets a receipt and reminders in their own language, so there are fewer disputes.",
          "<b>First segment:</b> Hindi-belt and Maharashtra towns, where udhaar is common and Hindi, Hinglish and Marathi are already supported.",
      ]),
      Paragraph("No credible national figure exists for the share of sales on credit or bad-debt losses; I will measure both in the pilot.", small))

slide("2 · COMPETITION", "Others make you type, or confirm on a screen",
      table([
          ["Product", "How entries are made", "Gap Khata Dost fills"],
          ["Khatabook (5 crore registered)", "Typed. Voice only as an outbound reminder call to the customer",
           "No voice entry by the owner. FY24 loss about Rs 116 Cr; shifting to lending"],
          ["OkCredit", "Typed or captured from UPI", "No voice input; FY25 loss Rs 23 Cr"],
          ["Vyapar", "Billing and inventory software", "Built for invoices, not quick udhaar at the counter"],
          ["VoiceKhata (100k+ installs)", "Voice to GST bill, checked on screen", "No spoken read-back or spoken yes; billing-first"],
          ["Khata Dost", "Spoken entry, spoken read-back, spoken yes",
           "Eyes-free loop, customer receipt in their language, amount cross-check, consent-first reminders"],
      ], [190, 300, 360]),
      Spacer(1, 6),
      Paragraph("Voice khata prototypes are common at hackathons. The difference is the trust layer and the customer side, "
                "both working end to end today.", small))

slide("3 · WHAT IT DEPENDS ON", "Every paid service has a fallback that keeps the core loop alive",
      table([
          ["Dependency (price checked 27 Nov 2026)", "If it gets costly or stops", "Status in the prototype"],
          ["Sarvam speech-to-text, Rs 0.49/min", "Browser speech recognition; open models (AI4Bharat IndicConformer, MIT)",
           "Browser fallback built and used when no key is set"],
          ["OpenAI gpt-4.1-mini, $0.40 / $1.60 per M tokens. Retires 14 Jan 2027",
           "One config line to swap models (Claude already wired in); rule parser works with no model at all",
           "Rule-only mode built and tested in CI"],
          ["Sarvam Bulbul text-to-speech, Rs 3 per 1,000 chars (about 74% of cost)",
           "Phone's own voice", "Built: used automatically without a key"],
          ["WhatsApp", "Templates cannot carry audio; opt-in required; debt collection is banned",
           "Messages are account updates from the shop's own number, consent and 8 am to 7 pm only"],
      ], [270, 320, 260]),
      Spacer(1, 6),
      Paragraph("<b>Cost:</b> about Rs 0.41 per entry with paid speech both ways (about Rs 400 per shop per month at 30 entries a day); "
                "about Rs 0.05 per entry using the phone's own voice. Estimates from published prices, assumed Rs 88 per USD.", body))

slide("3 · RISKS, STATED HONESTLY", "What could go wrong, and what is already done about it",
      *bullets([
          "<b>Mishearing in a noisy shop</b> is the biggest risk. If an amount is wrong even a few times, owners return to paper. "
          "Mitigation: read-back, two readers, digit-by-digit for big amounts, undo, and a learned noise floor in the recorder.",
          "<b>Adoption.</b> Paper is free and familiar. Khata Dost must feel faster than paper on day one, so the first screen is just one button.",
          "<b>WhatsApp policy.</b> Reminders could be rejected as collection. They are framed as an account statement, sent only with consent, "
          "only 8 am to 7 pm, and every message says how to stop them.",
          "<b>Privacy (DPDP Act).</b> Core duties start around May 2027 and the shop owner is responsible for customer data. The app already "
          "records each customer's consent with a timestamp and stores only name, phone, amounts, items and dates.",
          "<b>Market shift.</b> Quick commerce is closing some metro kiranas; the first segment is smaller towns.",
          "<b>Prototype limits:</b> single shop, no login, no offline queue yet, WhatsApp sending is a share link, not the Business API.",
      ]))

slide("4 · LAUNCH PLAN", "Start in one market lane, prove the numbers, then spread through distributors",
      table([
          ["When", "What", "How I will know"],
          ["Weeks 1 to 2", "10 shops in one neighbourhood; I sit at the counter and watch real entries",
           "Owners finish entries unaided; entries per day; errors caught by read-back"],
          ["Weeks 3 to 10", "Pilot with 50 shops", "70% still using it in week 8; median entry under 6 s; 95% saved correctly; "
           "overdue udhaar (over 30 days) down 25% against a week-1 baseline from each paper khata"],
          ["Next", "FMCG distributor salesmen and kirana associations onboard shops; UPI QR installers as a second channel",
           "Cost per active shop; reminder opt-out rate"],
      ], [120, 380, 350]),
      Spacer(1, 6),
      Paragraph("<b>Model:</b> the ledger is free; reminders and multi-staff use are a small monthly fee once the pilot shows "
                "recovered money is larger than the fee.", body),
      Paragraph("<b>User testing so far:</b> [TODO: number of shop owners who tried it, and what they said]", body))

slide("WHAT IS REAL TODAY", "Built, tested, and honest about the rest",
      table([
          ["Working end to end", "Simulated or planned"],
          ["Voice entry, read-back, spoken yes, corrections, undo, balances, \"kis kis ka baaki\" (Hindi, Hinglish, Marathi, English)",
           "WhatsApp Business API sending (prototype uses a WhatsApp share link and a downloadable voice note)"],
          ["Customer receipts and reminders in the customer's language, consent with timestamp, 8 am to 7 pm rule",
           "Other Indian languages beyond Hindi, Marathi and English replies"],
          ["Keyless mode, Docker one-command start, 53 automated tests, CI that starts the container with no keys",
           "Multi-shop accounts, login, offline queue, backups"],
      ], [425, 425]),
      Spacer(1, 6),
      Paragraph("Demo data (Ramesh, Sunita, Ganesh) is synthetic and labelled. Stack: FastAPI, SQLite, Sarvam saaras and bulbul, "
                "OpenAI or Claude for extraction, plain HTML and JS.", small))

if S and isinstance(S[-1], PageBreak):
    S.pop()

doc = BaseDocTemplate(str(OUT), pagesize=(W, H), leftMargin=40, rightMargin=40, topMargin=34, bottomMargin=36,
                      title="Khata Dost pitch", author="Khata Dost")
doc.addPageTemplates([PageTemplate(id="s", frames=[Frame(40, 36, W - 80, H - 70, id="f")], onPage=footer)])
doc.build(S)
print(f"wrote {OUT}")
