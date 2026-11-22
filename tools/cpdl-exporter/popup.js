const statusEl = document.getElementById("status");
const goBtn = document.getElementById("go");

function waitComplete(tabId) {
  return new Promise((resolve) => {
    const listener = (id, info) => {
      if (id === tabId && info.status === "complete") {
        chrome.tabs.onUpdated.removeListener(listener);
        resolve();
      }
    };
    chrome.tabs.onUpdated.addListener(listener);
    setTimeout(() => {
      chrome.tabs.onUpdated.removeListener(listener);
      resolve();
    }, 15000);
  });
}

async function ensureTab() {
  const tabs = await chrome.tabs.query({ url: "https://www.cpdl.org/*" });
  if (tabs.length) {
    return tabs[0];
  }
  const tab = await chrome.tabs.create({
    url: "https://www.cpdl.org/wiki/index.php?title=Special:Export",
  });
  await waitComplete(tab.id);
  return tab;
}

// Se ejecuta EN la página de cpdl.org (same-origin, con cookies/cf_clearance).
async function exportInPage() {
  const base = "https://www.cpdl.org/wiki/api.php";
  const params = new URLSearchParams({
    action: "query",
    export: "1",
    generator: "allpages",
    gaplimit: "500",
    format: "json",
  });
  const parts = [];
  for (let i = 0; i < 2000; i++) {
    const r = await fetch(base + "?" + params.toString(), { credentials: "include" });
    const text = await r.text();
    if (!r.ok) {
      return { error: "HTTP " + r.status, hint: text.slice(0, 120) };
    }
    let j;
    try {
      j = JSON.parse(text);
    } catch (e) {
      return { error: "respuesta no-JSON (challenge?)", hint: text.slice(0, 120) };
    }
    if (j.query && j.query.export) {
      parts.push(j.query.export);
    }
    if (!j.continue) {
      break;
    }
    for (const [k, v] of Object.entries(j.continue)) {
      params.set(k, v);
    }
  }
  const blob = new Blob([JSON.stringify(parts)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "cpdl-parts.json";
  a.click();
  return { parts: parts.length };
}

goBtn.addEventListener("click", async () => {
  goBtn.disabled = true;
  statusEl.textContent = "Preparando pestaña de cpdl.org…";
  try {
    const tab = await ensureTab();
    await new Promise((r) => setTimeout(r, 1500));
    statusEl.textContent = "Exportando… (mantén esta ventana abierta)";
    const res = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: exportInPage,
    });
    const out = res && res[0] && res[0].result;
    statusEl.textContent =
      out && out.error
        ? "Error: " + out.error + " " + (out.hint || "")
        : "Hecho: " + JSON.stringify(out);
  } catch (e) {
    statusEl.textContent = "Error: " + e.message;
  } finally {
    goBtn.disabled = false;
  }
});
