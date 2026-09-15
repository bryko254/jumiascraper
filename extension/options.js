const input = document.getElementById("api-base");
const msg = document.getElementById("msg");

(async () => {
  input.value = await getApiBase();
})();

document.getElementById("save").addEventListener("click", async () => {
  const value = input.value.trim().replace(/\/$/, "") || DEFAULT_API;
  try {
    const origin = new URL(value).origin;
    if (!origin.includes("localhost") && !origin.includes("127.0.0.1")) {
      await chrome.permissions.request({ origins: [`${origin}/*`] });
    }
  } catch (err) {
    msg.textContent = `Invalid URL: ${err.message}`;
    msg.classList.add("error");
    return;
  }
  await chrome.storage.sync.set({ apiBaseUrl: value });
  msg.classList.remove("error");
  try {
    const health = await api("/health");
    msg.textContent = `Saved. API is ${health.status}.`;
  } catch (err) {
    msg.textContent = `Saved, but health check failed: ${err.message}`;
    msg.classList.add("error");
  }
});
