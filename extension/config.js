// Default API base URL for docker compose.
// For a packed production build, set this to your Railway public HTTPS origin
// (Settings → Networking on the `api` service), e.g.:
//   const DEFAULT_API = "https://api-xxxx.up.railway.app";
const DEFAULT_API = "http://127.0.0.1:8001";

async function getApiBase() {
  const stored = await chrome.storage.sync.get({ apiBaseUrl: DEFAULT_API });
  return String(stored.apiBaseUrl || DEFAULT_API).replace(/\/$/, "");
}

async function api(path, options = {}) {
  const base = await getApiBase();
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };
  const response = await fetch(`${base}${path}`, { ...options, headers });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      try {
        detail = await response.text();
      } catch {
        /* ignore */
      }
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  if (response.status === 204) {
    return null;
  }
  return response.json();
}

function formatMoney(amount, currency) {
  if (amount === null || amount === undefined || Number.isNaN(Number(amount))) {
    return "—";
  }
  const code = currency || "";
  const number = Number(amount).toLocaleString(undefined, { maximumFractionDigits: 2 });
  return code ? `${code} ${number}` : number;
}

function alertModeLabel(mode) {
  if (mode === "price_up") return "Price up";
  if (mode === "price_down") return "Price down";
  return "Any change";
}
