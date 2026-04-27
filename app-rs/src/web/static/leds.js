// Dashboard LEDs panel: poll /api/leds at 0.4 s with 600 ms afterglow on
// transition true→false, render GPIO-test buttons that POST /api/leds/test.

(function () {
  const root = document.getElementById("leds");
  if (!root) return;

  const gpioLabel = document.getElementById("leds-gpios");
  const testRoot = document.getElementById("leds-test");
  const testStatus = document.getElementById("leds-test-status");

  const AFTERGLOW_MS = 600;
  const lastOn = { green: 0, orange: 0, red: 0 };

  async function tick() {
    try {
      const r = await fetch("/api/leds", { cache: "no-store" });
      if (!r.ok) return;
      const j = await r.json();

      const now = Date.now();
      for (const c of ["green", "orange", "red"]) {
        if (j.state[c]) lastOn[c] = now;
      }
      for (const span of root.querySelectorAll(".led")) {
        const c = span.dataset.color;
        const lit = j.state[c] || (now - lastOn[c] < AFTERGLOW_MS);
        span.classList.toggle("on", !!lit);
      }
      // Per-bulb hint text (shows the GPIO each bulb is mapped to).
      for (const hint of root.querySelectorAll(".led__hint")) {
        const c = hint.dataset.gpio;
        if (j.gpios && j.gpios[c] != null) hint.textContent = `gpio ${j.gpios[c]}`;
      }
      if (gpioLabel && j.gpios) {
        gpioLabel.textContent =
          `mapped — green = gpio ${j.gpios.green} · orange = gpio ${j.gpios.orange} · red = gpio ${j.gpios.red}`;
      }
      if (testRoot && testRoot.childElementCount === 0 && Array.isArray(j.test_gpios)) {
        renderTestButtons(j.test_gpios, j.gpios);
      }
    } catch { /* swallow transient fetch errors */ }
  }

  function renderTestButtons(gpios, mapping) {
    const byGpio = {};
    if (mapping) for (const [c, g] of Object.entries(mapping)) byGpio[g] = c;
    for (const gpio of gpios) {
      const btn = document.createElement("button");
      btn.type = "button";
      const hint = byGpio[gpio] ? ` · ${byGpio[gpio]}` : "";
      btn.textContent = `gpio ${gpio}${hint}`;
      btn.addEventListener("click", () => testGpio(gpio, btn));
      testRoot.appendChild(btn);
    }
  }

  async function testGpio(gpio, btn) {
    btn.disabled = true;
    setStatus(`driving gpio ${gpio} for 5 s — watch the board`, "warn");
    try {
      const fd = new FormData();
      fd.set("gpio", gpio);
      fd.set("duration_ms", "5000");
      const r = await fetch("/api/leds/test", { method: "POST", body: fd });
      if (!r.ok) throw new Error(await r.text());
      await new Promise(res => setTimeout(res, 5200));
      setStatus(`gpio ${gpio}: done — which colour lit up?`, "ok");
    } catch (e) {
      setStatus(`gpio ${gpio}: failed — ${e.message || e}`, "err");
    } finally {
      btn.disabled = false;
    }
  }

  function setStatus(text, kind) {
    if (!testStatus) return;
    testStatus.innerHTML = "";
    const span = document.createElement("span");
    span.className = "status " + (kind || "");
    span.textContent = text;
    testStatus.appendChild(span);
  }

  tick();
  setInterval(tick, 400);
})();
