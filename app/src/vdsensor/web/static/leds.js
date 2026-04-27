// Polls /api/leds at 0.4 s and toggles a CSS class on each LED dot.
// "Afterglow": once we observe state=true for a colour, the dot stays lit
// for at least AFTERGLOW_MS so 80 ms hardware blinks are still catchable
// at our polling rate. Without this, the dashboard looks dead between
// blinks even when telegrams are arriving normally.
(function () {
  const root = document.getElementById("leds");
  const gpioLabel = document.getElementById("leds-gpios");
  const testRoot = document.getElementById("leds-test");
  const testStatus = document.getElementById("leds-test-status");
  if (!root) return;

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
      if (gpioLabel && j.gpios) {
        gpioLabel.textContent =
          `Mapped GPIOs — green=${j.gpios.green}, orange=${j.gpios.orange}, red=${j.gpios.red}`;
      }
      if (testRoot && testRoot.childElementCount === 0 && j.test_gpios) {
        renderTestButtons(j.test_gpios, j.gpios);
      }
    } catch { /* ignore */ }
  }

  function renderTestButtons(gpios, mapping) {
    // Reverse map gpio→color for hint labels.
    const byGpio = {};
    if (mapping) for (const [c, g] of Object.entries(mapping)) byGpio[g] = c;
    for (const gpio of gpios) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "led-test-btn";
      const hint = byGpio[gpio] ? ` (mapped to ${byGpio[gpio]})` : "";
      btn.textContent = `GPIO ${gpio}${hint}`;
      btn.addEventListener("click", () => testGpio(gpio, btn));
      testRoot.appendChild(btn);
    }
  }

  async function testGpio(gpio, btn) {
    btn.disabled = true;
    if (testStatus) testStatus.textContent = `driving GPIO ${gpio} high for 5 s — watch the board…`;
    try {
      const fd = new FormData();
      fd.set("gpio", gpio);
      fd.set("duration_ms", "5000");
      const r = await fetch("/api/leds/test", { method: "POST", body: fd });
      if (!r.ok) throw new Error(await r.text());
      // re-enable after the drive finishes; add a 200 ms grace.
      await new Promise(res => setTimeout(res, 5200));
      if (testStatus) testStatus.textContent = `GPIO ${gpio}: done. Which colour lit up?`;
    } catch (e) {
      if (testStatus) {
        testStatus.textContent = `GPIO ${gpio}: failed — ${e.message || e}`;
        testStatus.classList.add("warn");
      }
    } finally {
      btn.disabled = false;
    }
  }

  tick();
  setInterval(tick, 400);
})();
