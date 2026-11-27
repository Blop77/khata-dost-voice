// Khata Dost front end: one tap to speak, read-back, then "haan" (heard automatically in hands-free mode).
const $ = (id) => document.getElementById(id);
const SESSION = (crypto.randomUUID && crypto.randomUUID()) || String(Date.now() + Math.random());
const BCP = { "hi-IN": "hi-IN", "mr-IN": "mr-IN", "en-IN": "en-IN" };
let config = { speech: false, llm: null };
let state = { lang: (window.I18N && window.I18N.lang === "en") ? "en-IN" : "hi-IN", awaiting: null, busy: false };
let rec = null; // active recording
const I = window.I18N || { lang: "hi", t: (k) => k, set() {}, apply() {} };
const t = (k, v) => I.t(k, v);
let SESSION_ID = SESSION;
const Motion = window.Motion || { on: false, intro() {}, say: (el, t) => (el.textContent = t), draft: (c, a, v) => (a.textContent = v ? "₹" + v : "₹ ?"),
  saved: (c, s, done) => done && done(), number: (el, v, p = "") => (el.textContent = p + "₹" + Number(v).toLocaleString("en-IN")), list() {}, pop() {} };
let listsShown = false;
const AVATAR = ["#b45309", "#0f766e", "#7c3aed", "#be123c", "#1d4ed8", "#4d7c0f", "#c2410c", "#0e7490"];
const avatarColor = (name) => AVATAR[[...name].reduce((a, c) => a + c.charCodeAt(0), 0) % AVATAR.length];
function setLevel(v) { $("micWrap").style.setProperty("--level", Math.max(0, Math.min(1, v)).toFixed(3)); }

// ---------- small helpers ----------
const rupees = (n) => "₹" + Number(n).toLocaleString("en-IN");
const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
const fmtDate = (iso) => iso ? new Date(iso + "T00:00:00").toLocaleDateString(t("locale"), { weekday: "short", day: "numeric", month: "short" }) : "";
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
    setStatus(t("noMic") + " (" + e.message + ")");
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
    setLevel((rms - noise) / Math.max(0.08, noise * 6)); // the rings swell with the owner's voice
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
    if (cancelled) { setStatus(auto ? t("heardNothingAuto") : ""); return; }
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
  if (!SR) { setStatus(t("noSR")); return; }
  const sr = new SR();
  sr.lang = BCP[state.lang] || t("speechLang");
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
  sr.onerror = (e) => setStatus(e.error === "no-speech" ? t("heardNothing") : t("srError") + e.error);
  sr.onend = () => { rec = null; micIdle(); if (!got && !auto) setStatus(t("heardNothing")); };
  sr.start();
  micRecording(auto);
}

function micRecording(auto) {
  $("micWrap").classList.add("rec");
  $("micWrap").classList.remove("idle-hint");
  if (!config.speech) setLevel(0.45); // browser recognition gives no levels; show a steady ring
  $("mic").classList.add("rec");
  $("micLabel").textContent = auto ? t("sayYes") : t("listening");
  setStatus(auto ? t("sayYesNo") : t("speakNow"));
}
function micIdle() {
  $("micWrap").classList.remove("rec");
  setLevel(0);
  $("mic").classList.remove("rec");
  $("micLabel").textContent = t("mic");
}

// ---------- talking to the server ----------
async function sendTurn(form) {
  if (state.busy) return;
  state.busy = true;
  $("mic").classList.add("busy");
  setStatus(t("thinking"));
  form.append("session", SESSION_ID);
  form.append("ui_lang", I.lang === "en" ? "en-IN" : "hi-IN");
  try {
    const res = await fetch("/api/khata/turn", { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || res.statusText);
    render(data);
    const secs = data.timing_ms ? ` · ${(data.timing_ms.total / 1000).toFixed(1)}s` : "";
    setStatus((data.source === "ai+rules" ? t("checkedBoth") : t("checkedRules")) + secs);
    speak(data.reply, data.lang, () => {
      // Hands-free: after a read-back, listen for "haan" without another tap.
      if ($("handsfree").checked && ["confirm", "confirm_new_customer", "undo_confirm", "which_customer", "amount_check"].includes(data.awaiting)) {
        startRecording({ auto: true });
      }
    });
    if (data.saved || data.undone) refreshLedger(data.saved && data.saved.customer && data.saved.customer.id);
  } catch (e) {
    // A dropped connection (server stopped, tunnel restarted) shows as a TypeError from fetch.
    setStatus(e instanceof TypeError ? t("offline") : e.message);
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
  Motion.say($("botSays"), d.reply);
  $("heard").textContent = d.transcript ? `${t("youSaid")}: "${d.transcript}"` : "";

  const draft = d.draft;
  const card = $("draft");
  if (d.saved && !card.hidden) {
    // Stamp the card that was just confirmed, then fold it away.
    Motion.saved(card, $("stamp"), () => { card.hidden = true; $("draftAmount").dataset.v = 0; });
  } else if (draft && draft.name) {
    const isNew = card.hidden || $("draftName").textContent !== draft.name;
    card.hidden = false;
    card.className = "draft " + (draft.type || "");
    $("draftName").textContent = draft.name;
    $("draftType").textContent = draft.type === "jama" ? t("jama") : draft.type === "udhaar" ? t("udhaar") : "?";
    $("draftType").className = "badge " + (draft.type || "");
    if (isNew) $("draftAmount").dataset.v = 0;
    Motion.draft(card, $("draftAmount"), draft.amount, isNew);
    $("draftMeta").textContent = [draft.items, draft.due_date && t("due") + ": " + fmtDate(draft.due_date)].filter(Boolean).join(" · ");
    const checks = $("draftChecks");
    checks.innerHTML = "";
    if (draft.new_customer || (!draft.customer_id && d.awaiting === "confirm_new_customer")) checks.append(el("span", "", t("newCustomer")));
    for (const f of d.item_fixes || []) checks.append(el("span", "", `${t("fixed")}: ${f}`));
    $("yesBtn").hidden = !["confirm", "confirm_new_customer"].includes(d.awaiting);
  } else {
    card.hidden = true;
    $("draftAmount").dataset.v = 0;
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
    $("receiptWa").textContent = c.phone ? t("waSend") : t("waNoNum");
    Motion.pop($("receipt"));
  }
  if (d.view === "customer" && d.customer) showDetail(d.customer.id);
  if (d.view === "reminders" || d.view === "dues") refreshLedger();
}

async function refreshLedger(flashId) {
  const data = await (await fetch("/api/khata/ledger")).json();
  $("shop").textContent = data.shop;
  Motion.number($("totalDue"), data.total_due);
  $("windowNote").textContent = data.reminder_window_open ? t("windowOpen") : t("windowClosed");

  const ul = $("customers");
  ul.innerHTML = "";
  for (const c of data.customers) {
    const li = el("li", "click");
    if (c.id === flashId) li.classList.add("flash");
    const row = el("div", "cust");
    const left = el("div", "who");
    const av = el("span", "avatar", [...c.name][0].toUpperCase());
    av.style.background = avatarColor(c.name);
    const txt = el("div");
    txt.append(el("strong", "", c.name));
    if (c.due_date && c.balance > 0) txt.append(el("div", "muted small", t("due") + ": " + fmtDate(c.due_date)));
    left.append(av, txt);
    const amt = el("span", "amt " + (c.balance > 0 ? "owe" : "clear"), c.balance > 0 ? rupees(c.balance) : c.balance < 0 ? "+" + rupees(-c.balance) : t("clear"));
    row.append(left, amt);
    li.append(row);
    li.onclick = () => showDetail(c.id);
    ul.append(li);
  }

  const rl = $("reminders");
  rl.innerHTML = "";
  if (!data.reminders.length) rl.append(el("li", "muted", t("noneDue")));
  for (const r of data.reminders) {
    const li = el("li");
    const row = el("div", "cust");
    row.append(el("strong", "", r.name), el("span", "amt owe", rupees(r.balance)));
    li.append(row, el("p", "msg", r.text));
    const actions = el("div", "row");
    const play = el("button", "act", t("voice"));
    play.onclick = () => speak(r.text, r.language);
    actions.append(play);
    if (r.consent && r.phone && data.reminder_window_open) {
      const a = el("a", "wa", t("waShort"));
      a.href = waLink(r.phone, r.text);
      a.target = "_blank"; a.rel = "noopener";
      actions.append(a);
    } else {
      actions.append(el("span", "muted small", !r.phone ? t("noPhone") : !r.consent ? t("noConsent") : t("sendHours")));
    }
    if (config.speech) {
      const dl = el("a", "act", t("voiceNote"));
      dl.href = `/api/tts?${new URLSearchParams({ text: r.text, lang: r.language })}`;
      dl.download = `yaad-${r.name}.mp3`;
      actions.append(dl);
    }
    li.append(actions);
    rl.append(li);
  }
  if (!listsShown) { listsShown = true; Motion.list([...ul.children, ...rl.children]); }
}

async function showDetail(id) {
  const c = await (await fetch(`/api/khata/customer/${id}`)).json();
  const box = $("detail");
  box.hidden = false;
  box.dataset.id = id;
  $("detailName").textContent = c.name;
  $("detailBalance").textContent = c.balance > 0 ? `${t("owes")} ${rupees(c.balance)}` : c.balance < 0 ? `${t("advance")} ${rupees(-c.balance)}` : t("settled");
  $("detailPhone").value = c.phone ? c.phone.replace(/^91/, "") : "";
  $("detailLang").value = c.language || "hi-IN";
  $("detailConsent").checked = !!c.reminder_consent;
  $("detailConsentAt").textContent = c.consent_at ? `${t("saidYesAt")}: ${new Date(c.consent_at).toLocaleString(t("locale"))}` : "";
  const ul = $("detailEntries");
  ul.innerHTML = "";
  for (const e of c.entries) {
    const li = el("li");
    const row = el("div", "cust");
    row.append(el("span", "", `${e.type === "jama" ? t("jama") : t("udhaar")} · ${new Date(e.created_at).toLocaleDateString(t("locale"))}${e.items ? " · " + e.items : ""}`),
               el("span", "amt " + (e.type === "jama" ? "clear" : "owe"), (e.type === "jama" ? "−" : "+") + rupees(e.amount)));
    li.append(row);
    if (e.heard && e.heard !== "(demo data)") li.append(el("div", "muted small", `${t("heardAs")}: "${e.heard}"`));
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
  let res = await fetch("/api/khata/reset-demo", { method: "POST" });
  if (res.status === 403) { // public link: the owner sets RESET_PIN
    const form = new FormData();
    form.append("pin", prompt("Reset PIN") || "");
    res = await fetch("/api/khata/reset-demo", { method: "POST", body: form });
  }
  if (res.ok) location.reload(); else setStatus(t("resetFailed") + " (" + res.status + ")");
};

function renderModes() {
  const m = $("modes");
  m.innerHTML = "";
  const part = (on, onText, offLabel, offText) => {
    if (on) return document.createTextNode(onText);
    const s = el("span");
    s.append(el("span", "warn", offLabel + " " + t("keyNotSet")), document.createTextNode(" → " + offText));
    return s;
  };
  m.append(part(config.speech, t("modeSpeechOn"), "Sarvam", t("modeSpeechOff")), document.createTextNode(" · "),
           part(config.llm, t("modeAiOn", { p: config.llm }), "AI", t("modeAiOff")));
}

// Switching language starts a fresh conversation in that language and re-labels the whole screen.
function switchLang(next) {
  if (next === I.lang) return;
  I.set(next);
  SESSION_ID = (crypto.randomUUID && crypto.randomUUID()) || String(Date.now() + Math.random());
  state.lang = next === "en" ? "en-IN" : "hi-IN";
  $("draft").hidden = true;
  $("optionsBox").hidden = true;
  $("heard").textContent = "";
  Motion.say($("botSays"), t("greeting"));
  micIdle();
  setStatus("");
  renderModes();
  refreshLedger();
  if ($("detail").dataset.id && !$("detail").hidden) showDetail($("detail").dataset.id);
}

(async function init() {
  config = await (await fetch("/api/config")).json();
  const notes = [];
  renderModes();
  I.apply();
  for (const b of document.querySelectorAll(".lang-switch button")) b.onclick = () => switchLang(b.dataset.lang);
  Motion.intro();
  refreshLedger();
})();
