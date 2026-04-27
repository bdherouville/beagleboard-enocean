// Pairing wizard: open /ws/pair, render dedup'd candidates, per-row
// inline-form posts /pair/assign with paired/updated success messaging.

(function () {
  const stateBox = document.getElementById("pair-state");
  const stateText = document.getElementById("pair-state-text");
  const tbody = document.querySelector("#candidates tbody");
  const startForm = document.getElementById("pair-start-form");
  const cancelBtn = document.getElementById("pair-cancel");
  const tpl = document.getElementById("assign-template");
  const statusBox = document.getElementById("pair-status");
  if (!stateBox || !tbody || !startForm || !cancelBtn || !tpl) return;

  function setStatus(html, kind) {
    if (!statusBox) return;
    statusBox.innerHTML = "";
    const div = document.createElement("div");
    div.className = "status " + (kind || "");
    div.innerHTML = html;
    statusBox.appendChild(div);
  }

  function setState(value) {
    stateBox.dataset.state = value;
    stateText.textContent = value;
  }

  function appendCandidate(p) {
    if (tbody.querySelector(`tr[data-sender="${p.sender}"]`)) return;

    // First candidate replaces the empty placeholder row.
    const empty = tbody.querySelector(".tbl-empty");
    if (empty) empty.remove();

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
        let body = {};
        try { body = await resp.json(); } catch {}
        const verb = body.created === false ? "updated" : "paired";
        setStatus(
          `✓ ${verb} ${p.sender} — ` +
          `<a href="/devices/${p.sender}">view in devices</a>`,
          "ok"
        );
        tr.remove();
      } else {
        const text = await resp.text();
        setStatus(`assign failed — ${text}`, "err");
      }
    });

    const dbm = p.dbm == null ? "—" : p.dbm + " dBm";
    tr.innerHTML = `
      <td class="col-sender"><code>${p.sender}</code></td>
      <td><code>${p.rorg}</code></td>
      <td>${dbm}</td>
      <td class="col-payload"><code>${p.payload}</code></td>
      <td class="right"></td>`;
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
    tbody.innerHTML = '<tr class="tbl-empty"><td colspan="5">[ window open · waiting for teach-in ]</td></tr>';
    setStatus("learn window opening…", "warn");
    const fd = new FormData(startForm);
    const resp = await fetch("/pair/start", { method: "POST", body: fd });
    if (resp.ok) {
      const j = await resp.json();
      setState("open");
      setStatus(`learn window open · ${(j.timeout_ms / 1000).toFixed(0)} s`, "ok");
    } else {
      const text = await resp.text();
      setStatus(`start failed — ${text}`, "err");
    }
  });

  cancelBtn.addEventListener("click", async () => {
    const resp = await fetch("/pair/cancel", { method: "POST" });
    if (resp.ok) {
      setState("closed");
      setStatus("learn window cancelled", "warn");
    }
  });
})();
