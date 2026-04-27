// Live telegram stream (/telegrams page) + global UTC clock for the chrome.
// Self-contained, no deps.

(function () {
  // -------- chrome clock ------------------------------------------------
  const localTime = document.getElementById("local-time");
  if (localTime) {
    const tick = () => {
      const d = new Date();
      const pad = n => String(n).padStart(2, "0");
      localTime.textContent =
        `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())}`;
    };
    tick();
    setInterval(tick, 1000);
  }

  // -------- live telegrams ---------------------------------------------
  const tbody = document.querySelector("#telegrams tbody");
  if (!tbody) return;

  const status = document.getElementById("ws-status");
  const countEl = document.getElementById("tele-count");
  const sendersEl = document.getElementById("tele-senders");
  const lastEl = document.getElementById("tele-last");

  const MAX_ROWS = 500;
  const senders = new Set();
  let count = 0;
  let backoff = 1000;
  let initialised = false;

  function setStatus(text, state) {
    if (!status) return;
    status.textContent = text;
    status.className = "pill";
    if (state) status.classList.add("pill--" + state);
  }

  function rssiBars(dbm) {
    if (dbm == null) return '<span class="muted">—</span>';
    // -50 dBm → 5 bars; -100 dBm → 1 bar. Clamp.
    const mapped = Math.max(1, Math.min(5, Math.round((dbm + 100) / 12)));
    let bars = '<span class="rssi__bars">';
    for (let i = 1; i <= 5; i++) {
      const cls = i <= mapped ? "lit-" + i : "";
      const h = 3 + i * 1.4;
      bars += `<i class="${cls}" style="height:${h}px"></i>`;
    }
    bars += "</span>";
    return `<span class="rssi">${bars}<span>${dbm}</span></span>`;
  }

  function appendRow(msg) {
    if (!initialised) {
      tbody.innerHTML = "";
      initialised = true;
    }
    const p = msg.payload;
    const tr = document.createElement("tr");
    tr.className = "tele-row-new";
    const t = msg.ts.replace("T", " ").replace("Z", "");
    tr.innerHTML = `
      <td class="col-time">${t}</td>
      <td class="col-rorg"><code>${p.rorg}</code></td>
      <td class="col-sender"><code>${p.sender}</code></td>
      <td class="col-status"><code>${p.status}</code></td>
      <td class="col-rssi">${rssiBars(p.dbm)}</td>
      <td class="col-payload"><code>${p.payload}</code></td>`;
    tbody.prepend(tr);
    while (tbody.rows.length > MAX_ROWS) tbody.deleteRow(tbody.rows.length - 1);

    count += 1;
    senders.add(p.sender);
    if (countEl) countEl.textContent = count.toString();
    if (sendersEl) sendersEl.textContent = senders.size.toString();
    if (lastEl) lastEl.textContent = t;
  }

  function connect() {
    setStatus("connecting…", "warn");
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${location.host}/ws/live`);

    ws.addEventListener("open", () => {
      setStatus("connected", "ok");
      backoff = 1000;
    });

    ws.addEventListener("message", (e) => {
      let msg;
      try { msg = JSON.parse(e.data); } catch { return; }
      if (msg.type !== "telegram") return;
      appendRow(msg);
    });

    ws.addEventListener("close", () => {
      setStatus(`disconnected · retry ${(backoff / 1000).toFixed(1)}s`, "err");
      setTimeout(connect, backoff);
      backoff = Math.min(backoff * 2, 30000);
    });
    ws.addEventListener("error", () => ws.close());
  }
  connect();
})();
