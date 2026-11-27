// Interface language for Khata Dost: Hindi (default) or English. The conversation itself still answers in
// whatever language the owner speaks; this only changes the screen text and the default reply language.
(function () {
  const S = {
    hi: {
      title: "खाता दोस्त", sub: "Khata Dost", totalDue: "कुल बाकी", greeting: "नमस्ते! बोलिए, किस ग्राहक का हिसाब लिखना है?",
      tagSpeak: "01 / बोलिए · Speak", yes: "✓ हाँ, लिखो", no: "✗ नहीं", stamp: "लिख दिया ✓", mic: "बोलिए", micAria: "बोलने के लिए दबाएँ",
      handsfree: "हाथ खाली नहीं? \"हाँ\" अपने-आप सुनूँगा", typePh: "या लिखें: Ramesh ko 250 udhaar", send: "भेजें", tryLabel: "बोलकर देखिए:",
      receiptTag: "ग्राहक की रसीद · Customer receipt", play: "▶ सुनें", waSend: "WhatsApp पर भेजें", waNoNum: "WhatsApp पर भेजें (नंबर नहीं है)",
      receiptNote: "ग्राहक को उसकी भाषा में रसीद, ताकि बाद में झगड़ा न हो।",
      tagDue: "02 / आज की याद · Due today", tagCust: "03 / खाता · Customers", close: "बंद करें", phone: "फ़ोन", lang: "भाषा",
      consent: "ग्राहक ने WhatsApp याद दिलाने के लिए \"हाँ\" कहा", save: "सेव करें", tagTrust: "04 / भरोसा · Why you can trust it",
      trust1: "बिना आपके \"हाँ\" के कुछ भी सेव नहीं होता।", trust2: "बोली गई रकम डेटाबेस से आती है, AI से नहीं।",
      trust3: "AI key हो तो नियम + AI दोनों रकम मिलाते हैं; अलग हों तो पूछता है।", trust4: "याद सिर्फ़ उन्हें, जिन्होंने हाँ कहा; सुबह 8 से शाम 7 बजे तक।",
      reset: "डेमो फिर से शुरू करें (reset demo data)",
      chips: ["रमेश को ढाई सौ का उधार, आटा 5 किलो, सोमवार तक", "Sunita ne 400 jama kiya", "किस किस का पैसा बाकी है?",
              "Mohan ko 2 packet chicks, 40 rupaye udhaar", "पिछली entry हटाओ", "aaj kisko yaad dilana hai"],
      noMic: "माइक नहीं मिला। नीचे लिखकर भेजें।", heardNothingAuto: "कुछ नहीं सुना। ✓ / ✗ दबाएँ या फिर से बोलें।",
      noSR: "इस ब्राउज़र में आवाज़ पहचान नहीं है। नीचे लिखकर भेजें।", heardNothing: "कुछ नहीं सुना। फिर से बोलें।", srError: "आवाज़ पहचान: ",
      sayYes: "\"हाँ\" बोलिए…", listening: "सुन रहा हूँ…", sayYesNo: "हाँ / नहीं बोलिए", speakNow: "बोलिए, रुकते ही भेज दूँगा",
      thinking: "समझ रहा हूँ…", checkedBoth: "AI + नियम दोनों ने जाँचा", checkedRules: "नियमों से समझा (AI key नहीं)",
      youSaid: "आपने कहा", udhaar: "उधार", jama: "जमा", due: "तारीख़", newCustomer: "🆕 नया ग्राहक", fixed: "🔁 सुधारा",
      windowOpen: "भेजने का समय: अभी ठीक है", windowClosed: "भेजने का समय: सुबह 8 – शाम 7", clear: "✓ साफ़",
      noneDue: "आज किसी की तारीख़ नहीं है।", voice: "▶ आवाज़", waShort: "WhatsApp भेजें", noPhone: "फ़ोन नंबर नहीं",
      noConsent: "ग्राहक की हाँ नहीं", sendHours: "सुबह 8 – शाम 7 भेजें", voiceNote: "⬇ वॉइस नोट", owes: "बाकी", advance: "आगाऊ",
      offline: "सर्वर से कनेक्शन नहीं हुआ। इंटरनेट देखें या पेज फिर से खोलें।", settled: "हिसाब साफ़ ✓", saidYesAt: "हाँ कहा", heardAs: "सुना था", resetFailed: "Reset नहीं हुआ",
      modeSpeechOn: "आवाज़: Sarvam (हिन्दी, मराठी, Hinglish…)", modeSpeechOff: "ब्राउज़र की आवाज़ पहचान",
      modeAiOn: "समझ: AI ({p}) + नियम", modeAiOff: "सिर्फ़ नियम (Hindi/Hinglish/Marathi/English)", keyNotSet: "key not set",
      locale: "hi-IN", speechLang: "hi-IN",
    },
    en: {
      title: "Khata Dost", sub: "खाता दोस्त", totalDue: "Total due", greeting: "Namaste! Whose account shall I write?",
      tagSpeak: "01 / Speak", yes: "✓ Yes, save", no: "✗ No", stamp: "Saved ✓", mic: "Speak", micAria: "Tap to speak",
      handsfree: "Hands busy? I'll listen for \"yes\" on my own", typePh: "Or type: Ramesh, 250 rupees credit", send: "Send", tryLabel: "Try saying:",
      receiptTag: "Customer receipt", play: "▶ Play", waSend: "Send on WhatsApp", waNoNum: "Send on WhatsApp (no number)",
      receiptNote: "A receipt in the customer's own language, so there is no argument later.",
      tagDue: "02 / Due today", tagCust: "03 / Customers", close: "Close", phone: "Phone", lang: "Language",
      consent: "Customer said yes to WhatsApp reminders", save: "Save", tagTrust: "04 / Why you can trust it",
      trust1: "Nothing is saved without your \"yes\".", trust2: "Amounts you hear come from the ledger, never from the AI.",
      trust3: "With an AI key, rules and AI both check the amount; if they disagree, it asks.", trust4: "Reminders only to customers who agreed, 8 am to 7 pm.",
      reset: "Reset demo data",
      chips: ["Ramesh, 250 rupees credit, atta 5 kilo, pay by Monday", "Sunita paid 400", "Who owes me money?",
              "Mohan, 2 packet chicks, 40 rupees credit", "Delete the last entry", "Who should I remind today?"],
      noMic: "No microphone found. Type below instead.", heardNothingAuto: "Didn't hear anything. Tap ✓ / ✗ or speak again.",
      noSR: "This browser has no speech recognition. Type below instead.", heardNothing: "Didn't hear anything. Please speak again.", srError: "Speech recognition: ",
      sayYes: "Say \"yes\"…", listening: "Listening…", sayYesNo: "Say yes / no", speakNow: "Speak; I'll send when you stop",
      thinking: "Thinking…", checkedBoth: "Checked by AI + rules", checkedRules: "Understood by rules (no AI key)",
      youSaid: "You said", udhaar: "Credit", jama: "Paid", due: "Due", newCustomer: "🆕 New customer", fixed: "🔁 Corrected",
      windowOpen: "Sending hours: open now", windowClosed: "Sending hours: 8 am – 7 pm", clear: "✓ Clear",
      noneDue: "Nobody is due today.", voice: "▶ Voice", waShort: "Send WhatsApp", noPhone: "No phone number",
      noConsent: "No customer consent", sendHours: "Send 8 am – 7 pm", voiceNote: "⬇ Voice note", owes: "Owes", advance: "Advance",
      offline: "Can't reach the server. Check the connection or reopen the page.", settled: "All settled ✓", saidYesAt: "Said yes", heardAs: "Heard", resetFailed: "Reset failed",
      modeSpeechOn: "Voice: Sarvam (Hindi, Marathi, English…)", modeSpeechOff: "browser speech recognition",
      modeAiOn: "Understanding: AI ({p}) + rules", modeAiOff: "rules only (Hindi/Hinglish/Marathi/English)", keyNotSet: "key not set",
      locale: "en-IN", speechLang: "en-IN",
    },
  };

  let lang = "hi";
  try { lang = localStorage.getItem("khata-ui") === "en" ? "en" : "hi"; } catch (e) { /* private mode: default Hindi */ }

  const I18N = {
    get lang() { return lang; },
    t(key, vars) {
      let s = (S[lang] && S[lang][key]) ?? S.hi[key] ?? key;
      if (vars && typeof s === "string") for (const [k, v] of Object.entries(vars)) s = s.replace(`{${k}}`, v);
      return s;
    },
    set(next) {
      lang = next === "en" ? "en" : "hi";
      try { localStorage.setItem("khata-ui", lang); } catch (e) { /* ignore */ }
      I18N.apply();
    },
    // Fill every element marked data-i18n / data-i18n-ph / data-i18n-aria.
    apply() {
      document.documentElement.lang = lang;
      for (const e of document.querySelectorAll("[data-i18n]")) e.textContent = I18N.t(e.dataset.i18n);
      for (const e of document.querySelectorAll("[data-i18n-ph]")) e.placeholder = I18N.t(e.dataset.i18nPh);
      for (const e of document.querySelectorAll("[data-i18n-aria]")) e.setAttribute("aria-label", I18N.t(e.dataset.i18nAria));
      const chips = I18N.t("chips");
      document.querySelectorAll(".chip").forEach((c, i) => { if (chips[i]) c.textContent = chips[i]; });
      for (const b of document.querySelectorAll(".lang-switch button")) b.setAttribute("aria-pressed", String(b.dataset.lang === lang));
    },
  };
  window.I18N = I18N;
})();
