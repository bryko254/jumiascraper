const HOST_COUNTRY = {
  "jumia.com.eg": { code: "eg", name: "Egypt" },
  "jumia.com.gh": { code: "gh", name: "Ghana" },
  "jumia.ci": { code: "ci", name: "Ivory Coast" },
  "jumia.co.ke": { code: "ke", name: "Kenya" },
  "jumia.ma": { code: "ma", name: "Morocco" },
  "jumia.com.ng": { code: "ng", name: "Nigeria" },
  "jumia.sn": { code: "sn", name: "Senegal" },
  "jumia.ug": { code: "ug", name: "Uganda" },
};

function countryFromHost(host) {
  const bare = host.replace(/^www\./, "");
  return HOST_COUNTRY[bare] || null;
}

function isProductPage(pathname) {
  return pathname.toLowerCase().endsWith(".html");
}

function pageInfo() {
  const country = countryFromHost(location.hostname);
  const titleNode = document.querySelector("h1");
  const priceNode = document.querySelector(
    "span.-b.-fs24, span.-b.-ltr.-tal.-fs24, [itemprop='price'], .prc"
  );
  const ogTitle = document.querySelector("meta[property='og:title']");
  return {
    isJumia: Boolean(country),
    isProduct: Boolean(country) && isProductPage(location.pathname),
    url: `${location.origin}${location.pathname}`,
    title: (titleNode && titleNode.innerText.trim()) || (ogTitle && ogTitle.content) || document.title,
    priceText: priceNode ? priceNode.textContent.trim() : null,
    country: country && country.code,
    countryName: country && country.name,
  };
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message && message.type === "PAGE_INFO") {
    sendResponse(pageInfo());
  }
  return true;
});
