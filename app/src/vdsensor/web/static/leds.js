// Polls /api/leds at 0.4 s and toggles a CSS class on each LED dot.
// Light enough to keep up with TX/RX blink patterns without WebSockets.
(function () {
  const root = document.getElementById("leds");
  const gpioLabel = document.getElementById("leds-gpios");
  if (!root) return;

  async function tick() {
    try {
      const r = await fetch("/api/leds", { cache: "no-store" });
      if (!r.ok) return;
      const j = await r.json();
      for (const span of root.querySelectorAll(".led")) {
        const c = span.dataset.color;
        span.classList.toggle("on", !!j.state[c]);
      }
      if (gpioLabel && j.gpios) {
        gpioLabel.textContent =
          `GPIO mapping: green=${j.gpios.green}, orange=${j.gpios.orange}, red=${j.gpios.red}`;
      }
    } catch { /* ignore */ }
  }
  tick();
  setInterval(tick, 400);
})();
