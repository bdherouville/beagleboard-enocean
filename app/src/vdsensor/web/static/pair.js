// Pairing wizard glue: open WS, render candidates, wire start/cancel/assign.
(function () {
  const status = document.getElementById("pair-status");
  const tbody = document.querySelector("#candidates tbody");
  const startForm = document.getElementById("pair-start-form");
  const cancelBtn = document.getElementById("pair-cancel");
  const tpl = document.getElementById("assign-template");
  if (!status || !tbody || !startForm || !cancelBtn || !tpl) return;

  function setStatus(text, isError) {
    status.innerHTML = "state: <code>" + text + "</code>";
    status.classList.toggle("warn", !!isError);
  }

  function appendCandidate(p) {
    if (tbody.querySelector(`tr[data-sender="${p.sender}"]`)) return;
    const tr = document.createElement("tr");
    tr.dataset.sender = p.sender;
    const action = tpl.content.cloneNode(true);
    const form = action.querySelector("form");
    form.querySelector("input[name=sender_id]").value = p.sender;
    form.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const fd = new FormData(form);
      const resp = await fetch("/pair/assign", { method: "POST", body: fd });
      if (resp.ok) {
        setStatus("paired " + p.sender, false);
        tr.remove();
      } else {
        const text = await resp.text();
        setStatus("assign failed: " + text, true);
      }
    });
    tr.innerHTML = `
      <td><code>${p.sender}</code></td>
      <td>${p.rorg}</td>
      <td>${p.dbm ?? ""}</td>
      <td><code>${p.payload}</code></td>
      <td></td>`;
    tr.lastElementChild.appendChild(action);
    tbody.prepend(tr);
  }

  function connectWs() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${location.host}/ws/pair`);
    ws.addEventListener("message", (e) => {
      try {
        const msg = JSON.parse(e.data);
        if (msg.type === "learn_candidate") appendCandidate(msg.payload);
      } catch { /* ignore */ }
    });
    ws.addEventListener("close", () => setTimeout(connectWs, 2000));
    ws.addEventListener("error", () => ws.close());
  }
  connectWs();

  startForm.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    tbody.innerHTML = "";
    const fd = new FormData(startForm);
    const resp = await fetch("/pair/start", { method: "POST", body: fd });
    if (resp.ok) {
      const j = await resp.json();
      setStatus(`open (${j.timeout_ms}ms)`, false);
    } else {
      setStatus("start failed: " + await resp.text(), true);
    }
  });

  cancelBtn.addEventListener("click", async () => {
    const resp = await fetch("/pair/cancel", { method: "POST" });
    if (resp.ok) setStatus("cancelled", false);
  });
})();
