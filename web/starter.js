const $ = (id) => document.getElementById(id);
let config = null;
let history = [];
let recorder = null;
let chunks = [];

async function init() {
  config = await (await fetch("/api/config")).json();
  for (const [id, t] of Object.entries(config.tracks)) {
    $("track").add(new Option(t.title, id));
  }
  $("modes").textContent =
    `Speech: ${config.speech ? "Sarvam" : "mock (type instead)"} · Brain: ${config.llm || "mock"}`;
  $("track").onchange = reset;
  $("reset").onclick = reset;
  reset();
}

function reset() {
  history = [];
  $("log").innerHTML = "";
  $("fields").innerHTML = "";
  $("done").innerHTML = "";
  const greeting = config.tracks[$("track").value].greeting;
  addMsg("bot", greeting);
  history.push({ role: "assistant", text: greeting });
}

function addMsg(who, text, meta) {
  const el = document.createElement("div");
  el.className = `msg ${who}`;
  el.textContent = text;
  if (meta) {
    const s = document.createElement("small");
    s.textContent = meta;
    el.appendChild(s);
  }
  $("log").appendChild(el);
  $("log").scrollTop = $("log").scrollHeight;
}

function renderFields(fields, done) {
  $("fields").innerHTML = "";
  for (const [k, v] of Object.entries(fields || {})) {
    const dt = document.createElement("dt");
    dt.textContent = k.replaceAll("_", " ");
    const dd = document.createElement("dd");
    dd.textContent = v ?? "—";
    $("fields").append(dt, dd);
  }
  $("done").innerHTML = done ? '<div class="done">✓ Confirmed</div>' : "";
}

function browserSpeak(text, lang) {
  if (!("speechSynthesis" in window)) return;
  const u = new SpeechSynthesisUtterance(text);
  u.lang = lang;
  speechSynthesis.speak(u);
}

function speak(text, lang) {
  if (!config.speech) return browserSpeak(text, lang);
  // Streams MP3 from the server; playback starts as soon as the first chunk arrives.
  const audio = new Audio(`/api/tts?${new URLSearchParams({ text, lang })}`);
  audio.play().catch(() => browserSpeak(text, lang));
}

async function sendTurn(form) {
  form.append("track", $("track").value);
  form.append("history", JSON.stringify(history));
  $("mic").disabled = true;
  $("status").textContent = "Thinking…";
  try {
    const res = await fetch("/api/turn", { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || res.statusText);
    addMsg("user", data.transcript, data.language_code || undefined);
    addMsg("bot", data.reply);
    history.push({ role: "user", text: data.transcript }, { role: "assistant", text: data.reply });
    renderFields(data.fields, data.done);
    speak(data.reply, data.tts_language);
    $("status").textContent = "";
  } catch (e) {
    $("status").textContent = e.message;
  } finally {
    $("mic").disabled = false;
  }
}

$("mic").onclick = async () => {
  if (recorder && recorder.state === "recording") {
    recorder.stop();
    return;
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    recorder = new MediaRecorder(stream);
    chunks = [];
    recorder.ondataavailable = (e) => chunks.push(e.data);
    recorder.onstop = () => {
      stream.getTracks().forEach((t) => t.stop());
      $("mic").classList.remove("rec");
      $("mic").textContent = "Tap to talk";
      const type = recorder.mimeType || "audio/webm";
      const form = new FormData();
      form.append("audio", new Blob(chunks, { type }), type.includes("ogg") ? "speech.ogg" : "speech.webm");
      sendTurn(form);
    };
    recorder.start();
    $("mic").classList.add("rec");
    $("mic").textContent = "Tap to stop";
    $("status").textContent = "Listening…";
  } catch (e) {
    $("status").textContent = `Mic unavailable: ${e.message}`;
  }
};

$("typed").onsubmit = (e) => {
  e.preventDefault();
  const text = $("text").value.trim();
  if (!text) return;
  $("text").value = "";
  const form = new FormData();
  form.append("text", text);
  sendTurn(form);
};

init();
