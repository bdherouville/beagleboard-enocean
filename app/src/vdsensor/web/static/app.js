// Minimal WS client for /telegrams: append rows on incoming messages, reconnect with backoff.
(function () {
  const status = document.getElementById("ws-status");
  const tbody = document.querySelector("#telegrams tbody");
  if (!status || !tbody) return;

  const MAX_ROWS = 500;
  let backoff = 1000;

  function connect() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${location.host}/ws/live`);

    ws.addEventListener("open", () => {
      status.textContent = "connected";
      status.classList.remove("warn");
      backoff = 1000;
    });

    ws.addEventListener("message", (e) => {
      let msg;
      try { msg = JSON.parse(e.data); } catch { return; }
      if (msg.type !== "telegram") return;
      const p = msg.payload;
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${msg.ts.replace("T", " ").replace("Z", "")}</td>
        <td>${p.rorg}</td>
        <td>${p.sender}</td>
        <td>${p.status}</td>
        <td>${p.dbm ?? ""}</td>
        <td>${p.payload}</td>`;
      tbody.prepend(tr);
      while (tbody.rows.length > MAX_ROWS) tbody.deleteRow(tbody.rows.length - 1);
    });

    const onClose = () => {
      status.textContent = `disconnected; retrying in ${(backoff / 1000).toFixed(1)}s`;
      status.classList.add("warn");
      setTimeout(connect, backoff);
      backoff = Math.min(backoff * 2, 30000);
    };
    ws.addEventListener("close", onClose);
    ws.addEventListener("error", () => ws.close());
  }
  connect();
})();
