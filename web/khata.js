// Khata Dost front end: one tap to speak, read-back, then "haan" (heard automatically in hands-free mode).
const $ = (id) => document.getElementById(id);
const SESSION = (crypto.randomUUID && crypto.randomUUID()) || String(Date.now() + Math.random());
const BCP = { "hi-IN": "hi-IN", "mr-IN": "mr-IN", "en-IN": "en-IN" };
let config = { speech: false, llm: null };
let state = { lang: "hi-IN", awaiting: null, busy: false };
let rec = null; // active recording

// ---------- small helpers ----------
const rupees = (n) => "₹" + Number(n).toLocaleString("en-IN");
const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
const fmtDate = (iso) => iso ? new Date(iso + "T00:00:00").toLocaleDateString("hi-IN", { weekday: "short", day: "numeric", month: "short" }) : "";
const waLink = (phone, text) => `https://wa.me/${phone || ""}?text=${encodeURIComponent(text)}`;
function setStatus(t) { $("status").textContent = t || ""; }

// ---------- speaking ----------
function browserSpeak(text, lang, onend) {
  if (!("speechSynthesis" in window)) return onend && onend();
  speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.lang = BCP[lang] || "hi-IN";
  u.rate = 1.0;
  u.onend = () => onend && onend();
  u.onerror = () => onend && onend();
  speechSynthesis.speak(u);
}

let player = null;
function speak(text, lang, onend) {
  if (player) { player.pause(); player = null; }
  if (!config.speech) return browserSpeak(text, lang, onend);
  // Sarvam streams MP3; playback starts as soon as the first bytes arrive.
  player = new Audio(`/api/tts?${new URLSearchParams({ text, lang })}`);
  player.onended = () => onend && onend();
  player.onerror = () => browserSpeak(text, lang, onend);
  player.play().catch(() => browserSpeak(text, lang, onend));
}

// ---------- listening ----------
// Records until the owner stops talking (1.2 s of silence after speech), or 15 s, or a second tap.
async function startRecording({ auto = false } = {}) {
  if (state.busy || rec) return;
  if (!config.speech) return startBrowserRecognition({ auto });
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
  } catch (e) {
    setStatus("माइक नहीं मिला। नीचे लिखकर भेजें। (" + e.message + ")");
    return;
  }
  const mr = new MediaRecorder(stream);
  const chunks = [];
  const ctx = new (window.AudioContext || window.webkitAudioContext)();
  const analyser = ctx.createAnalyser();
  analyser.fftSize = 1024;
  ctx.createMediaStreamSource(stream).connect(analyser);
  const buf = new Float32Array(analyser.fftSize);
  let heardSpeech = false, quietSince = performance.now(), started = performance.now(), noise = 0.01;
  rec = { mr, stream, ctx, cancelled: false };

  const tick = () => {
    if (!rec || rec.mr !== mr) return;
    analyser.getFloatTimeDomainData(buf);
    let sum = 0; for (const v of buf) sum += v * v;
    const rms = Math.sqrt(sum / buf.length);
    const now = performance.now();
    if (now - started < 400) noise = Math.max(noise, rms); // learn the shop's background level
    const loud = rms > Math.max(0.02, noise * 2.2);
    if (loud) { heardSpeech = true; quietSince = now; }
    const quiet = now - quietSince;
    if ((heardSpeech && quiet > 1200) || now - started > 15000) return stopRecording();
    if (auto && !heardSpeech && now - started > 5000) { rec.cancelled = true; return stopRecording(); }
    requestAnimationFrame(tick);
  };
  mr.ondataavailable = (e) => e.data.size && chunks.push(e.data);
  mr.onstop = () => {
    const cancelled = rec && rec.cancelled;
    stream.getTracks().forEach((t) => t.stop());
    ctx.close();
    rec = null;
    micIdle();
    if (cancelled) { setStatus(auto ? "कुछ नहीं सुना। ✓ / ✗ दबाएँ या फिर से बोलें।" : ""); return; }
    const type = mr.mimeType || "audio/webm";
    const form = new FormData();
    form.append("audio", new Blob(chunks, { type }), type.includes("ogg") ? "speech.ogg" : type.includes("mp4") ? "speech.mp4" : "speech.webm");
    sendTurn(form);
  };
  mr.start(250);
  micRecording(auto);
  requestAnimationFrame(tick);
}

function stopRecording() {
  if (rec && rec.mr && rec.mr.state === "recording") rec.mr.stop();
  if (rec && rec.sr) rec.sr.stop();
}

// No Sarvam key: Chrome's built-in recognition keeps the app voice-first.
function startBrowserRecognition({ auto }) {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) { setStatus("इस ब्राउज़र में आवाज़ पहचान नहीं है। नीचे लिखकर भेजें।"); return; }
  const sr = new SR();
  sr.lang = BCP[state.lang] || "hi-IN";
  sr.interimResults = false;
  sr.maxAlternatives = 1;
  let got = false;
  rec = { sr };
  sr.onresult = (e) => {
    got = true;
    const form = new FormData();
    form.append("text", e.results[0][0].transcript);
    sendTurn(form);
  };
  sr.onerror = (e) => setStatus(e.error === "no-speech" ? "कुछ नहीं सुना।" : "आवाज़ पहचान: " + e.error);
  sr.onend = () => { rec = null; micIdle(); if (!got && !auto) setStatus("कुछ नहीं सुना। फिर से बोलें।"); };
  sr.start();
  micRecording(auto);
}

function micRecording(auto) {
  $("mic").classList.add("rec");
  $("micLabel").textContent = auto ? "\"हाँ\" बोलिए…" : "सुन रहा हूँ…";
  setStatus(auto ? "हाँ / नहीं बोलिए" : "बोलिए, रुकते ही भेज दूँगा");
}
function micIdle() {
  $("mic").classList.remove("rec");
  $("micLabel").textContent = "बोलिए";
}

// ---------- talking to the server ----------
async function sendTurn(form) {
  if (state.busy) return;
  state.busy = true;
  $("mic").classList.add("busy");
  setStatus("समझ रहा हूँ…");
  form.append("session", SESSION);
  try {
    const res = await fetch("/api/khata/turn", { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || res.statusText);
    render(data);
    const t = data.timing_ms ? ` · ${(data.timing_ms.total / 1000).toFixed(1)}s` : "";
    setStatus((data.source === "ai+rules" ? "AI + नियम दोनों ने जाँचा" : "नियमों से समझा (AI key नहीं)") + t);
    speak(data.reply, data.lang, () => {
      // Hands-free: after a read-back, listen for "haan" without another tap.
      if ($("handsfree").checked && ["confirm", "confirm_new_customer", "undo_confirm", "which_customer", "amount_check"].includes(data.awaiting)) {
        startRecording({ auto: true });
      }
    });
    if (data.saved || data.undone) refreshLedger(data.saved && data.saved.customer && data.saved.customer.id);
  } catch (e) {
    setStatus(e.message);
  } finally {
    state.busy = false;
    $("mic").classList.remove("busy");
  }
}

function sendText(text) {
  const form = new FormData();
  form.append("text", text);
  sendTurn(form);
}

// ---------- rendering ----------
function render(d) {
  state.lang = d.lang || state.lang;
  state.awaiting = d.awaiting;
  $("botSays").textContent = d.reply;
  $("heard").textContent = d.transcript ? `आपने कहा: "${d.transcript}"` : "";

  const draft = d.draft;
  const card = $("draft");
  if (draft && draft.name) {
    card.hidden = false;
    card.className = "draft " + (draft.type || "");
    $("draftName").textContent = draft.name;
    $("draftType").textContent = draft.type === "jama" ? "जमा" : draft.type === "udhaar" ? "उधार" : "?";
    $("draftType").className = "badge " + (draft.type || "");
    $("draftAmount").textContent = draft.amount ? rupees(draft.amount) : "₹ ?";
    $("draftMeta").textContent = [draft.items, draft.due_date && "तारीख़: " + fmtDate(draft.due_date)].filter(Boolean).join(" · ");
    const checks = $("draftChecks");
    checks.innerHTML = "";
    if (draft.new_customer || (!draft.customer_id && d.awaiting === "confirm_new_customer")) checks.append(el("span", "", "🆕 नया ग्राहक"));
    for (const f of d.item_fixes || []) checks.append(el("span", "", `🔁 सुधारा: ${f}`));
    $("yesBtn").hidden = !["confirm", "confirm_new_customer"].includes(d.awaiting);
  } else {
    card.hidden = true;
  }

  const box = $("optionsBox");
  box.innerHTML = "";
  box.hidden = !(d.options && d.options.length && d.awaiting === "which_customer");
  for (const o of d.options || []) {
    const b = el("button", "", o.name);
    b.onclick = () => sendText(o.name);
    box.append(b);
  }

  if (d.saved) {
    $("receipt").hidden = false;
    $("receiptText").textContent = d.saved.receipt;
    $("receiptPlay").onclick = () => speak(d.saved.receipt, d.saved.customer.language || "hi-IN");
    const c = d.saved.customer;
    $("receiptWa").href = waLink(c.phone, d.saved.receipt);
    $("receiptWa").textContent = c.phone ? "WhatsApp पर भेजें" : "WhatsApp पर भेजें (नंबर नहीं है)";
  }
  if (d.view === "customer" && d.customer) showDetail(d.customer.id);
  if (d.view === "reminders" || d.view === "dues") refreshLedger();
}

async function refreshLedger(flashId) {
  const data = await (await fetch("/api/khata/ledger")).json();
  $("shop").textContent = data.shop;
  $("totalDue").textContent = rupees(data.total_due);
  $("windowNote").textContent = data.reminder_window_open ? "भेजने का समय: अभी ठीक है" : "भेजने का समय: सुबह 8 – शाम 7";

  const ul = $("customers");
  ul.innerHTML = "";
  for (const c of data.customers) {
    const li = el("li", "click");
    if (c.id === flashId) li.classList.add("flash");
    const row = el("div", "cust");
    const left = el("div");
    left.append(el("strong", "", c.name));
    if (c.due_date && c.balance > 0) left.append(el("div", "muted small", "तारीख़: " + fmtDate(c.due_date)));
    const amt = el("span", "amt " + (c.balance > 0 ? "owe" : "clear"), c.balance > 0 ? rupees(c.balance) : c.balance < 0 ? "+" + rupees(-c.balance) : "✓ साफ़");
    row.append(left, amt);
    li.append(row);
    li.onclick = () => showDetail(c.id);
    ul.append(li);
  }

  const rl = $("reminders");
  rl.innerHTML = "";
  if (!data.reminders.length) rl.append(el("li", "muted", "आज किसी की तारीख़ नहीं है।"));
  for (const r of data.reminders) {
    const li = el("li");
    const row = el("div", "cust");
    row.append(el("strong", "", r.name), el("span", "amt owe", rupees(r.balance)));
    li.append(row, el("p", "msg", r.text));
    const actions = el("div", "row");
    const play = el("button", "act", "▶ आवाज़");
    play.onclick = () => speak(r.text, r.language);
    actions.append(play);
    if (r.consent && r.phone && data.reminder_window_open) {
      const a = el("a", "wa", "WhatsApp भेजें");
      a.href = waLink(r.phone, r.text);
      a.target = "_blank"; a.rel = "noopener";
      actions.append(a);
    } else {
      actions.append(el("span", "muted small", !r.phone ? "फ़ोन नंबर नहीं" : !r.consent ? "ग्राहक की हाँ नहीं" : "सुबह 8 – शाम 7 भेजें"));
    }
    if (config.speech) {
      const dl = el("a", "act", "⬇ वॉइस नोट");
      dl.href = `/api/tts?${new URLSearchParams({ text: r.text, lang: r.language })}`;
      dl.download = `yaad-${r.name}.mp3`;
      actions.append(dl);
    }
    li.append(actions);
    rl.append(li);
  }
}

async function showDetail(id) {
  const c = await (await fetch(`/api/khata/customer/${id}`)).json();
  const box = $("detail");
  box.hidden = false;
  box.dataset.id = id;
  $("detailName").textContent = c.name;
  $("detailBalance").textContent = c.balance > 0 ? `बाकी ${rupees(c.balance)}` : c.balance < 0 ? `आगाऊ ${rupees(-c.balance)}` : "हिसाब साफ़ ✓";
  $("detailPhone").value = c.phone ? c.phone.replace(/^91/, "") : "";
  $("detailLang").value = c.language || "hi-IN";
  $("detailConsent").checked = !!c.reminder_consent;
  $("detailConsentAt").textContent = c.consent_at ? `हाँ कहा: ${new Date(c.consent_at).toLocaleString("hi-IN")}` : "";
  const ul = $("detailEntries");
  ul.innerHTML = "";
  for (const e of c.entries) {
    const li = el("li");
    const row = el("div", "cust");
    row.append(el("span", "", `${e.type === "jama" ? "जमा" : "उधार"} · ${new Date(e.created_at).toLocaleDateString("hi-IN")}${e.items ? " · " + e.items : ""}`),
               el("span", "amt " + (e.type === "jama" ? "clear" : "owe"), (e.type === "jama" ? "−" : "+") + rupees(e.amount)));
    li.append(row);
    if (e.heard && e.heard !== "(demo data)") li.append(el("div", "muted small", `सुना था: "${e.heard}"`));
    ul.append(li);
  }
  box.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

// ---------- wiring ----------
$("mic").onclick = () => (rec ? stopRecording() : startRecording());
$("yesBtn").onclick = () => sendText("haan");
$("noBtn").onclick = () => sendText("nahi");
$("typed").onsubmit = (e) => {
  e.preventDefault();
  const t = $("text").value.trim();
  if (t) { $("text").value = ""; sendText(t); }
};
for (const chip of document.querySelectorAll(".chip")) chip.onclick = () => sendText(chip.textContent);
$("detailClose").onclick = () => { $("detail").hidden = true; };
$("detailForm").onsubmit = async (e) => {
  e.preventDefault();
  const id = $("detail").dataset.id;
  const form = new FormData();
  form.append("phone", $("detailPhone").value.trim());
  form.append("language", $("detailLang").value);
  form.append("consent", $("detailConsent").checked ? "true" : "false");
  await fetch(`/api/khata/customer/${id}`, { method: "POST", body: form });
  await showDetail(id);
  refreshLedger();
};
$("resetDemo").onclick = async () => {
  await fetch("/api/khata/reset-demo", { method: "POST" });
  location.reload();
};

(async function init() {
  config = await (await fetch("/api/config")).json();
  const notes = [];
  notes.push(config.speech ? "आवाज़: Sarvam (हिन्दी, मराठी, Hinglish…)" : '<span class="warn">Sarvam key not set</span> → ब्राउज़र की आवाज़ पहचान');
  notes.push(config.llm ? `समझ: AI (${config.llm}) + नियम` : '<span class="warn">AI key not set</span> → सिर्फ़ नियम (Hindi/Hinglish/Marathi)');
  $("modes").innerHTML = notes.join(" · ");
  refreshLedger();
})();
