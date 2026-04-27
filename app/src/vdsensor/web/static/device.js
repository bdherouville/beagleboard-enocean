// Polls /api/devices/<id>/state every second and refreshes the latest-values
// block + last-seen timestamps. No full page reload needed.
(function () {
  const id = window.VDSENSOR_DEVICE_ID;
  if (!id) return;

  const decodedEl = document.getElementById("dev-decoded");
  const lastSeenEl = document.getElementById("dev-last-seen");
  const rssiEl = document.getElementById("dev-rssi");

  function fmtValue(v) {
    if (v === true) return "yes";
    if (v === false) return "no";
    if (v === null || v === undefined) return "—";
    return String(v);
  }

  async function tick() {
    try {
      const r = await fetch(`/api/devices/${id}/state`, { cache: "no-store" });
      if (!r.ok) return;
      const j = await r.json();

      if (lastSeenEl) {
        lastSeenEl.textContent = j.last_ts
          ? j.last_ts.replace("T", " ").replace("Z", "") + " UTC"
          : "—";
      }
      if (rssiEl) {
        rssiEl.textContent = j.last_rssi != null ? `${j.last_rssi} dBm` : "—";
      }

      if (decodedEl) {
        decodedEl.innerHTML = "";
        if (j.decoded && Object.keys(j.decoded).length > 0) {
          for (const [k, v] of Object.entries(j.decoded)) {
            const dt = document.createElement("dt");
            dt.textContent = k;
            const dd = document.createElement("dd");
            dd.textContent = fmtValue(v);
            decodedEl.append(dt, dd);
          }
        } else {
          const dt = document.createElement("dt");
          dt.className = "muted";
          dt.textContent = j.last_ts
            ? "No decoder for this EEP — telegram was recorded raw"
            : "Waiting for the next telegram…";
          decodedEl.append(dt);
        }
      }
    } catch { /* ignore transient fetch errors */ }
  }
  tick();
  setInterval(tick, 1000);
})();
