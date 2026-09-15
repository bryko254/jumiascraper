"""Resilient Jumia product-page HTML parser.

Preference order:
1. JSON-LD Product / Offer (schema.org)
2. Open Graph / product meta tags
3. Visible CSS fallbacks used across Jumia storefronts
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from shared.countries import canonicalize_product_url, country_from_url
from shared.prices import parse_price

logger = logging.getLogger(__name__)


def _first_text(soup: BeautifulSoup, selectors: list[str]) -> Optional[str]:
    for selector in selectors:
        node = soup.select_one(selector)
        if node:
            text = node.get_text(" ", strip=True)
            if text:
                return text
    return None


def _attr(soup: BeautifulSoup, selector: str, attr: str) -> Optional[str]:
    node = soup.select_one(selector)
    if not node:
        return None
    value = node.get(attr)
    if isinstance(value, list):
        value = value[0] if value else None
    return value.strip() if isinstance(value, str) and value.strip() else None


def _json_ld_blocks(soup: BeautifulSoup) -> list[Any]:
    blocks: list[Any] = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text() or ""
        raw = raw.strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(data, list):
            blocks.extend(data)
        else:
            blocks.append(data)
    return blocks


def _walk_jsonld(node: Any) -> list[dict]:
    found: list[dict] = []
    if isinstance(node, list):
        for item in node:
            found.extend(_walk_jsonld(item))
        return found
    if not isinstance(node, dict):
        return found
    types = node.get("@type")
    type_list = types if isinstance(types, list) else [types]
    type_list = [str(t).lower() for t in type_list if t]
    if "product" in type_list:
        found.append(node)
    graph = node.get("@graph")
    if graph:
        found.extend(_walk_jsonld(graph))
    return found


def _offer_price(offers: Any) -> tuple[Optional[float], Optional[str], Optional[float]]:
    if isinstance(offers, list):
        for offer in offers:
            price, currency, listed = _offer_price(offer)
            if price is not None:
                return price, currency, listed
        return None, None, None
    if not isinstance(offers, dict):
        return None, None, None

    currency = offers.get("priceCurrency")
    price = parse_price(offers.get("price") or offers.get("lowPrice"))
    listed = None
    spec = offers.get("priceSpecification")
    specs = spec if isinstance(spec, list) else [spec] if spec else []
    for item in specs:
        if not isinstance(item, dict):
            continue
        ptype = str(item.get("priceType") or "")
        value = parse_price(item.get("price"))
        if "Strikethrough" in ptype or "ListPrice" in ptype:
            listed = value
        elif price is None:
            price = value
        currency = currency or item.get("priceCurrency")
    return price, currency, listed


def parse_product_html(html: str, page_url: str) -> Optional[dict]:
    """Extract a scrape-result dict from a Jumia product page. Returns None on failure."""
    if not html or not page_url:
        return None

    country = country_from_url(page_url)
    soup = BeautifulSoup(html, "html.parser")
    url = canonicalize_product_url(page_url)

    name: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = country.currency if country else None
    image_url: Optional[str] = None
    old_price: Optional[float] = None
    sku: Optional[str] = None
    category: Optional[str] = None
    discount: Optional[str] = None

    for block in _json_ld_blocks(soup):
        for product in _walk_jsonld(block):
            name = name or product.get("name")
            sku = sku or product.get("sku")
            image = product.get("image")
            if not image_url:
                if isinstance(image, list) and image:
                    image_url = image[0] if isinstance(image[0], str) else image[0].get("url")
                elif isinstance(image, str):
                    image_url = image
                elif isinstance(image, dict):
                    image_url = image.get("url") or image.get("contentUrl")
            brand = product.get("brand")
            if isinstance(brand, dict) and not category:
                category = brand.get("name")
            p, cur, listed = _offer_price(product.get("offers"))
            if p is not None:
                price = p
            if cur:
                currency = cur
            if listed is not None:
                old_price = listed

    if not name:
        name = _attr(soup, "meta[property='og:title']", "content") or _first_text(
            soup,
            ["h1", "h1.-fs20", "h1[data-name]", "[itemprop='name']"],
        )
    if name:
        name = name.replace(" | Jumia", "").replace(" | jumia", "").strip()
        # og:title is often "Name | Jumia Kenya"
        for suffix in (
            " | Jumia Kenya",
            " | Jumia Nigeria",
            " | Jumia Egypt",
            " | Jumia Ghana",
            " | Jumia Uganda",
            " | Jumia Morocco",
            " | Jumia Senegal",
            " | Jumia Côte d'Ivoire",
            " | Jumia Cote d'Ivoire",
        ):
            if name.endswith(suffix):
                name = name[: -len(suffix)].strip()

    if price is None:
        amount = _attr(soup, "meta[property='product:price:amount']", "content") or _attr(
            soup, "meta[property='og:price:amount']", "content"
        )
        price = parse_price(amount, country)
    if price is None:
        price_text = _first_text(
            soup,
            [
                "[itemprop='price']",
                "span.-b.-fs24",
                "span.-b.-ltr.-tal.-fs24",
                ".prc",
                "div.-hr.-mtxs.-pvs span.-b",
                "span[data-price]",
            ],
        )
        price = parse_price(price_text, country)

    if old_price is None:
        old_text = _first_text(
            soup,
            ["span.-tal.-gy5.-lthr", ".old", "[data-old-price]", "span.-lthr"],
        )
        old_price = parse_price(old_text, country)

    if not discount:
        discount = _first_text(soup, ["span.bdg._dsct", "div._dsct", ".bdg._dsct", "span.-prs"])

    if not image_url:
        image_url = (
            _attr(soup, "meta[property='og:image']", "content")
            or _attr(soup, "img.img", "data-src")
            or _attr(soup, "img.img", "src")
            or _attr(soup, "img[data-src]", "data-src")
        )
    if image_url:
        image_url = urljoin(url, image_url)

    if not currency and country:
        currency = country.currency

    if not name or price is None:
        logger.warning("Failed to parse product page %s (name=%s price=%s)", url, name, price)
        return None

    return {
        "product_url": url,
        "name": name.strip(),
        "price": float(price),
        "currency": currency,
        "image_url": image_url,
        "old_price": float(old_price) if old_price is not None else None,
        "discount": discount,
        "country": country.code if country else None,
        "category": category,
        "sku": sku,
    }
