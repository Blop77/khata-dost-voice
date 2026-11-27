# Demo video script (3 minutes or less)

**Goal:** show the product working by voice, end to end, and show that you built it by voice with Wispr Flow. Judges score what they see working, so keep narration short and let the app talk.

## Before you record

1. Start the app with the `voice-starter-mac` preview, then the `public-tunnel` preview. Open the link **on your phone**; a phone looks like a real counter.
2. Tap **"डेमो फिर से शुरू करें"** at the bottom, so the khata starts from Ramesh ₹500, Sunita ₹800, Ganesh ₹300.
3. Keep **hands-free confirm** on. Turn the phone volume up. Record in a reasonably quiet room, or at a real shop counter if one will let you.
4. Record the screen with sound (iPhone: Control Centre → Screen Recording, with the mic on). A second camera filming you at a "counter" makes it far stronger.
5. Do one full practice run and check that every line below works with your voice.

## Shot list

| Time | Show | Say / do |
|---|---|---|
| 0:00–0:12 | You at a counter, phone in hand | (to camera) "Every kirana runs on udhaar. And every evening, with both hands busy, udhaar gets lost. This is Khata Dost." |
| 0:12–0:40 | Phone screen. Tap the mic once | Say: **"रमेश को ढाई सौ का उधार, आटा पाँच किलो, सोमवार तक देगा"**. Let the app read it back. Without tapping, say **"हाँ"**. Point at the balance (₹750) and the customer receipt. |
| 0:40–0:55 | Same screen | Tap and say **"सुनीता ने तीन सौ जमा किया"**. When it reads back, say **"नहीं, चार सौ"**. It changes only the amount. Say **"हाँ"**. |
| 0:55–1:10 | Same screen | Tap and say **"Rmesh ko pachaas ka udhaar"**. It asks **"कौन से?"**. Say **"दूधवाला"**, then **"हाँ"**. |
| 1:10–1:25 | Same screen | Tap and say **"किस किस का पैसा बाकी है?"**. It speaks the list and the total. |
| 1:25–1:45 | Scroll to "आज की याद" | Tap and say **"आज किसको याद दिलाना है?"**. Tap **▶ आवाज़** on Ramesh's reminder, then tap **WhatsApp भेजें** to show the message opening in WhatsApp. Don't send it. |
| 1:45–2:05 | Same screen | Tap and say **"पिछली entry हटाओ"**, then **"हाँ"**. (Optional: a Marathi line, **"रमेशला अडीचशे उधार"**.) |
| 2:05–2:25 | The trust card, or a quick zoom | "It never saves without your 'haan'. The AI never speaks a number; balances come from the ledger. Two readers check every amount, and if they disagree it asks. Big amounts are read digit by digit." |
| 2:25–2:50 | Your laptop: editor plus the Wispr Flow bar | **Built by voice:** with Wispr Flow, dictate one real small change, e.g. add a phrase to the parser (see below), then reload and show it working. |
| 2:50–3:00 | Back to you | "Khata Dost. Bolo, khata likho. Code, deck and live link are in the description." |

### A safe Wispr Flow segment (about 20 seconds)

Open `app/parser.py`, put the cursor in the `UDHAAR` list, and dictate with Flow:
> *add "baad mein dega" and "बाद में देगा" to the udhaar words*

Or dictate the same request as a prompt to your AI coding tool. Save, reload the app, and say **"Mohan ko sau rupaye, baad mein dega"**. It now knows that means udhaar. Commit the change afterwards so the repo matches the video.

## Upload

- YouTube, **Unlisted** is fine. Title: "Khata Dost: voice udhaar ledger for kiranas (India Runs on Voice)".
- Put the GitHub link and the live link in the description.
- After uploading, paste the YouTube URL into `docs/make_deck.py` (`LINKS["video"]`) and rebuild the deck (`python docs/make_deck.py`).

## Before submitting: test with real users (the brief asks for this)

The brief says *"A few real users should finish the task unaided."* Ask 2 or 3 shop owners (or family members who keep a khata) to try it on your phone. Don't help them; just say "बोलकर उधार लिखिए". Note:
- how many finished an entry without help,
- what went wrong,
- one sentence each of what they said about it.

Put the results in the deck's Launch plan slide (`[TODO: …]` line). Real user evidence is what separates the top teams.
