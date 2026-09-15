const apiStatus = document.getElementById("api-status");
const pageCard = document.getElementById("page-card");
const notProduct = document.getElementById("not-product");
const pageTitle = document.getElementById("page-title");
const pagePrice = document.getElementById("page-price");
const pageCountry = document.getElementById("page-country");
const watchBtn = document.getElementById("watch-btn");
const watchMsg = document.getElementById("watch-msg");
const alertMode = document.getElementById("alert-mode");
const watchesEl = document.getElementById("tab-watches");
const alertsEl = document.getElementById("tab-alerts");
const alertCount = document.getElementById("alert-count");

let pageInfo = null;

document.getElementById("open-options").addEventListener("click", () => {
  chrome.runtime.openOptionsPage();
});

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    const name = tab.dataset.tab;
    watchesEl.classList.toggle("hidden", name !== "watches");
    alertsEl.classList.toggle("hidden", name !== "alerts");
  });
});

function showMsg(text, isError) {
  watchMsg.textContent = text;
  watchMsg.classList.toggle("error", Boolean(isError));
}

async function currentTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab;
}

async function loadPageInfo() {
  const tab = await currentTab();
  if (!tab?.id) return null;
  try {
    return await chrome.tabs.sendMessage(tab.id, { type: "PAGE_INFO" });
  } catch {
    return {
      isJumia: false,
      isProduct: false,
      url: tab.url || "",
      title: tab.title || "",
      priceText: null,
      countryName: null,
    };
  }
}

function renderPage(info) {
  if (info?.isProduct) {
    pageCard.classList.remove("hidden");
    notProduct.classList.add("hidden");
    pageTitle.textContent = info.title || "Jumia product";
    pagePrice.textContent = info.priceText || "Price will be confirmed after the first scrape";
    pageCountry.textContent = info.countryName ? `${info.countryName} · product page` : "Product page";
  } else {
    pageCard.classList.add("hidden");
    notProduct.classList.remove("hidden");
  }
}

async function refreshHealth() {
  try {
    const health = await api("/health");
    const base = await getApiBase();
    apiStatus.textContent = `${health.status} · ${base}`;
  } catch (err) {
    apiStatus.textContent = `API unreachable — check Settings (${err.message})`;
  }
}

function productThumb(url) {
  if (!url) return "";
  return `<img src="${url}" alt="" />`;
}

function renderWatches(watches) {
  if (!watches.length) {
    watchesEl.innerHTML = `<p class="empty">No watches yet. Open a Jumia product page and click Watch.</p>`;
    return;
  }
  watchesEl.innerHTML = watches
    .map((w) => {
      const p = w.product || {};
      return `<article class="item" data-id="${w.id}">
        ${productThumb(p.image_url)}
        <div class="meta">
          <h3 title="${p.name || ""}">${p.name || "Unknown product"}</h3>
          <p class="muted">${formatMoney(p.current_price, p.currency)} · ${alertModeLabel(w.alert_mode)} · ${(p.country || "").toUpperCase()}</p>
        </div>
        <button class="danger unwatch">Remove</button>
      </article>`;
    })
    .join("");

  watchesEl.querySelectorAll(".unwatch").forEach((btn) => {
    btn.addEventListener("click", async (event) => {
      const id = event.target.closest(".item").dataset.id;
      try {
        await api(`/watches/${id}`, { method: "DELETE" });
        await loadLists();
      } catch (err) {
        showMsg(err.message, true);
      }
    });
  });
}

function renderAlerts(alerts) {
  const unread = alerts.filter((a) => !a.read).length;
  if (unread) {
    alertCount.textContent = String(unread);
    alertCount.classList.remove("hidden");
  } else {
    alertCount.classList.add("hidden");
  }
  chrome.action.setBadgeText({ text: unread ? String(unread) : "" });

  if (!alerts.length) {
    alertsEl.innerHTML = `<p class="empty">No alerts yet. After a watched price moves, it will show up here.</p>`;
    return;
  }
  alertsEl.innerHTML = alerts
    .map((a) => {
      const cls = a.direction === "down" ? "dir-down" : "dir-up";
      const label = a.direction === "down" ? "dropped" : "rose";
      return `<article class="item" data-id="${a.id}">
        <div class="meta">
          <h3 title="${a.product_name || ""}">${a.product_name || "Product"}</h3>
          <p class="${cls}">${label} ${formatMoney(a.old_price, a.currency)} → ${formatMoney(a.new_price, a.currency)}</p>
          <p class="muted">${a.read ? "Read" : "New"} · ${a.delivery_status}</p>
        </div>
      </article>`;
    })
    .join("");

  alertsEl.querySelectorAll(".item").forEach((item) => {
    item.addEventListener("click", async () => {
      try {
        await api(`/alerts/${item.dataset.id}`, {
          method: "PATCH",
          body: JSON.stringify({ read: true }),
        });
        await loadLists();
      } catch {
        /* ignore */
      }
    });
  });
}

async function loadLists() {
  try {
    const [watches, alerts] = await Promise.all([api("/watches"), api("/alerts?limit=30")]);
    renderWatches(watches);
    renderAlerts(alerts);
  } catch (err) {
    watchesEl.innerHTML = `<p class="empty">Could not load watches: ${err.message}</p>`;
    alertsEl.innerHTML = `<p class="empty">Could not load alerts: ${err.message}</p>`;
  }
}

watchBtn.addEventListener("click", async () => {
  if (!pageInfo?.isProduct || !pageInfo.url) {
    showMsg("This tab is not a Jumia product page.", true);
    return;
  }
  watchBtn.disabled = true;
  showMsg("Saving watch…");
  try {
    await api("/watches", {
      method: "POST",
      body: JSON.stringify({
        product_url: pageInfo.url,
        alert_mode: alertMode.value,
        name: pageInfo.title,
      }),
    });
    showMsg("Watching. The server will scrape this URL and store alerts in-API.");
    await loadLists();
  } catch (err) {
    showMsg(err.message, true);
  } finally {
    watchBtn.disabled = false;
  }
});

(async function init() {
  pageInfo = await loadPageInfo();
  renderPage(pageInfo);
  await refreshHealth();
  await loadLists();
})();
