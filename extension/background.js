importScripts("config.js");

async function refreshBadge() {
  try {
    const alerts = await api("/alerts?unread_only=true&limit=50");
    const n = Array.isArray(alerts) ? alerts.length : 0;
    await chrome.action.setBadgeBackgroundColor({ color: "#f68b1e" });
    await chrome.action.setBadgeText({ text: n ? String(n) : "" });
  } catch {
    await chrome.action.setBadgeText({ text: "" });
  }
}

chrome.runtime.onInstalled.addListener(() => {
  chrome.alarms.create("refresh-alerts", { periodInMinutes: 2 });
  refreshBadge();
});

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "refresh-alerts") {
    refreshBadge();
  }
});

chrome.runtime.onStartup.addListener(refreshBadge);
