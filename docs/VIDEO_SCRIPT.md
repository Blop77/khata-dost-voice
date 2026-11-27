# Khata Dost: full video script (about 2:55)

Key:
- **YOU (to camera):** narration. Speak calmly, at an Indian-English or Hinglish pace.
- **🎙 SAY TO APP:** tap the mic once, then speak naturally.
- **🔊 APP SAYS:** wait for the app to finish talking before you go on.
- **👉 DO:** an action on screen.

Before recording: reset the demo, keep hands-free on, turn the volume up.

---

### 0:00–0:15 · The problem (you on camera, at a counter if possible)

**YOU:**
"Every kirana in India runs on udhaar. Customers buy on credit, and the owner writes it in a paper khata, while weighing atta, with a customer waiting. In the evening rush, entries get missed, and at month end there are arguments. Typing apps don't help, because his hands are busy. So I built Khata Dost: you just say it."

### 0:15–0:45 · The main flow (switch to the phone screen)

**YOU:** "Watch. One tap, and I speak like I would at the counter."

🎙 **SAY TO APP:** "रमेश को ढाई सौ का उधार, आटा पाँच किलो, सोमवार तक देगा।"

🔊 **APP SAYS:** "Ramesh, उधार 250 रुपये, aata 5 kilo, सोमवार 30 नवंबर तक। लिख दूँ?"

**YOU (quickly):** "It reads it back. I don't touch the phone. I just say yes."

🎙 **SAY TO APP:** "हाँ।"

🔊 **APP SAYS:** "लिख दिया। Ramesh का कुल बाकी 750 रुपये।"

👉 **DO:** point at the "लिख दिया" stamp, the new total, and the receipt.

**YOU:** "Saved, the balance updated, and Ramesh gets a receipt in his own language."

### 0:45–1:05 · Fixing a mistake by voice

**YOU:** "What if the amount is wrong?"

🎙 **SAY TO APP:** "सुनीता ने तीन सौ जमा किया।"

🔊 **APP SAYS:** "Sunita, जमा 300 रुपये। लिख दूँ?"

🎙 **SAY TO APP:** "नहीं, चार सौ।"

🔊 **APP SAYS:** "Sunita, जमा 400 रुपये। लिख दूँ?"

🎙 **SAY TO APP:** "हाँ।"

**YOU:** "It changed only the amount. Nothing gets saved without my yes."

### 1:05–1:25 · It never guesses a customer

**YOU:** "Two customers with the same name? It asks instead of guessing."

🎙 **SAY TO APP:** "Rmesh ko pachaas ka udhaar."

🔊 **APP SAYS:** "कौन से? Ramesh, Ramesh doodhwala"

🎙 **SAY TO APP:** "दूधवाला।"

🔊 **APP SAYS:** "Ramesh doodhwala, उधार 50 रुपये। लिख दूँ?"

🎙 **SAY TO APP:** "हाँ।"

### 1:25–1:40 · Who owes money

**YOU:** "And the question every owner asks:"

🎙 **SAY TO APP:** "किस किस का पैसा बाकी है?"

🔊 **APP SAYS:** "...लोगों के कुल ... रुपये बाकी। Ramesh ..., Sunita ..." (it reads the list)

### 1:40–2:00 · Reminders

🎙 **SAY TO APP:** "आज किसको याद दिलाना है?"

🔊 **APP SAYS:** "2 लोगों की तारीख़ आ गई: Ramesh, Sunita…"

👉 **DO:** scroll to "आज की याद". Tap **▶ आवाज़** on Ramesh, let it play for 2 seconds, then tap **WhatsApp भेजें** to show it opening. Don't send.

**YOU:** "A polite reminder in the customer's language, only to customers who said yes, and only between 8 am and 7 pm."

### 2:00–2:20 · Why you can trust it (zoom in on the dark card at the bottom)

**YOU:**
"A khata is money, so trust comes first. Nothing saves without your 'haan'. The AI never speaks a number; every amount comes from the ledger. Two separate readers check each amount, and if they disagree, it asks. And it even works without any AI key."

### 2:20–2:45 · Built by voice with Wispr Flow (laptop screen)

**YOU:** "I built all of this by voice with Wispr Flow. Let me teach it a new phrase, right now."

👉 **DO:** open `app/parser.py`, click inside the `UDHAAR = [` list, hold the Flow key and say:

> "add baad mein chuka dega comma"

👉 **DO:** check it typed `"baad mein chuka dega",` inside the list. Save, then reload the app.

🎙 **SAY TO APP:** "Mohan ko sau rupaye, baad mein chuka dega."

🔊 **APP SAYS:** "Mohan नया ग्राहक है। सही?" → 🎙 "हाँ" → it reads back **उधार 100 रुपये**

**YOU:** "Spoken, understood, done."

### 2:45–2:55 · Close (back to you on camera)

**YOU:**
"Khata Dost. Bolo, khata likho. Built for the 1.2 crore kiranas that still run on paper. The code, the deck and a live link are in the description. Thank you."

---

## Tips

- If the app mishears you, say **"नहीं"** and repeat. That recovery is worth keeping in the video.
- Leave 1 second of silence after each line, so it sends automatically.
- If you run over 3:00, cut the reminders section (1:40–2:00) first.
- After recording, commit the parser change you dictated so the GitHub code matches the video.
