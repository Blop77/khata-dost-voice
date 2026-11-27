// Motion for Khata Dost. Every effect marks a moment that matters at the counter: the app heard you,
// here is the entry, it is saved, the balance changed. With no GSAP (offline) or reduced motion, all are no-ops.
(function () {
  const reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const g = !reduce && window.gsap ? window.gsap : null;
  const rupees = (n) => "₹" + Math.round(n).toLocaleString("en-IN");

  const M = {
    on: !!g,

    // Page entrance: header first, then the talk card, then the side cards.
    intro() {
      if (!g) return;
      const tl = g.timeline({ defaults: { ease: "power3.out" } });
      tl.from(".seal", { y: 6, opacity: 0, duration: 0.5 })
        .from(".top h1, .tagline, .shop", { y: 14, opacity: 0, duration: 0.6, stagger: 0.08 }, "-=0.45")
        .from(".total", { y: 14, opacity: 0, duration: 0.6 }, "-=0.5")
        .from(".talk", { y: 30, opacity: 0, duration: 0.8 }, "-=0.35")
        .from(".mic-wrap", { scale: 0.92, opacity: 0, duration: 0.6 }, "-=0.45")
        .from(".side > .card", { y: 30, opacity: 0, duration: 0.7, stagger: 0.1 }, "-=0.55");
    },

    // The app's sentence arrives word by word (whole words, so Devanagari ligatures stay intact).
    say(el, text) {
      if (!g) { el.textContent = text; return; }
      el.textContent = "";
      const words = text.split(/(\s+)/).map((w) => {
        if (/^\s+$/.test(w)) return document.createTextNode(w);
        const s = document.createElement("span");
        s.className = "w";
        s.textContent = w;
        return s;
      });
      words.forEach((n) => el.appendChild(n));
      g.from(el.querySelectorAll(".w"), { y: 8, opacity: 0, duration: 0.35, stagger: 0.035, ease: "power2.out" });
    },

    // A new or changed entry card pops in; the amount counts up so the eye lands on it.
    draft(card, amountEl, amount, isNew) {
      if (!g) { amountEl.textContent = amount ? rupees(amount) : "₹ ?"; return; }
      if (isNew) g.fromTo(card, { y: 18, scale: 0.97, opacity: 0 }, { y: 0, scale: 1, opacity: 1, duration: 0.5, ease: "power3.out" });
      else g.fromTo(card, { x: -6 }, { x: 0, duration: 0.4, ease: "elastic.out(1, 0.4)" });
      if (!amount) { amountEl.textContent = "₹ ?"; return; }
      const from = { v: Number(amountEl.dataset.v || 0) };
      amountEl.dataset.v = amount;
      g.to(from, { v: amount, duration: 0.6, ease: "power2.out", onUpdate: () => (amountEl.textContent = rupees(from.v)) });
    },

    // Saved: an ink stamp lands on the card, then the card folds away.
    saved(card, stamp, done) {
      if (!g) { done && done(); return; }
      g.timeline({ onComplete: () => { g.set(stamp, { opacity: 0 }); done && done(); } })
        .fromTo(stamp, { opacity: 0, scale: 2.2, rotate: -24 }, { opacity: 1, scale: 1, rotate: -12, duration: 0.35, ease: "power4.in" })
        .to(card, { x: 3, duration: 0.05, yoyo: true, repeat: 3 }, ">-0.02")
        .to(card, { opacity: 0, y: -10, height: 0, marginTop: 0, paddingTop: 0, paddingBottom: 0, duration: 0.45, ease: "power2.in", delay: 0.7 })
        .set(card, { clearProps: "all" });
    },

    // Any rupee figure ticks to its new value.
    number(el, value, prefix = "") {
      const target = Number(value) || 0;
      if (!g || el.dataset.v === undefined) { el.dataset.v = target; el.textContent = prefix + rupees(target); return; }
      const from = { v: Number(el.dataset.v) };
      el.dataset.v = target;
      g.to(from, { v: target, duration: 0.8, ease: "power2.out", onUpdate: () => (el.textContent = prefix + rupees(from.v)) });
      g.fromTo(el, { scale: 1.12 }, { scale: 1, duration: 0.6, ease: "power3.out" });
    },

    // Lists reveal with a short stagger the first time, and only the changed row flashes later.
    list(items) {
      if (!g || !items.length) return;
      g.from(items, { y: 12, opacity: 0, duration: 0.45, stagger: 0.06, ease: "power2.out" });
    },

    pop(el) {
      if (!g || !el) return;
      g.fromTo(el, { y: 12, opacity: 0 }, { y: 0, opacity: 1, duration: 0.5, ease: "power3.out" });
    },
  };
  window.Motion = M;
})();
