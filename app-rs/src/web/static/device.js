// Device detail polling: refresh "Latest decoded values" + last-seen + RSSI
// every second from /api/devices/<id>/state.

(function () {
  const id = window.VDSENSOR_DEVICE_ID;
  if (!id) return;

  const decodedEl = document.getElementById("dev-decoded");
  const lastSeenEl = document.getElementById("dev-last-seen");
  const rssiEl = document.getElementById("dev-rssi");

  function fmtValue(v) {
    if (v === true) return { text: "yes", cls: "decoded__val--bool-on" };
    if (v === false) return { text: "no", cls: "decoded__val--bool-off" };
    if (v === null || v === undefined) return { text: "—", cls: "decoded__val--null" };
    if (typeof v === "string") return { text: v, cls: "decoded__val--str" };
    return { text: String(v), cls: "" };
  }

  function fmtKey(k) {
    return k.replace(/_/g, " ");
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
        lastSeenEl.classList.toggle("muted", !j.last_ts);
      }
      if (rssiEl) {
        rssiEl.textContent = j.last_rssi != null ? `${j.last_rssi} dBm` : "—";
        rssiEl.classList.toggle("muted", j.last_rssi == null);
      }

      if (decodedEl) {
        decodedEl.innerHTML = "";
        const entries = j.decoded ? Object.entries(j.decoded) : [];
        if (entries.length === 0) {
          const empty = document.createElement("div");
          empty.className = "decoded__item";
          empty.innerHTML = `
            <div class="decoded__key">awaiting</div>
            <div class="decoded__val decoded__val--null">${j.last_ts ? '— no decoder' : '— first frame'}</div>`;
          decodedEl.appendChild(empty);
        } else {
          for (const [k, v] of entries) {
            const f = fmtValue(v);
            const item = document.createElement("div");
            item.className = "decoded__item";
            const key = document.createElement("div");
            key.className = "decoded__key";
            key.textContent = fmtKey(k);
            const val = document.createElement("div");
            val.className = "decoded__val " + f.cls;
            val.textContent = f.text;
            item.append(key, val);
            decodedEl.appendChild(item);
          }
        }
      }
    } catch { /* ignore */ }
  }
  tick();
  setInterval(tick, 1000);
})();
