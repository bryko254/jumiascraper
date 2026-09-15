"""Jumia market catalogue: eight countries, domains, currencies, URL helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse, urlunparse


@dataclass(frozen=True)
class Country:
    code: str
    name: str
    host: str
    currency: str
    currency_symbols: tuple[str, ...]
    tld: str


COUNTRIES: dict[str, Country] = {
    "eg": Country(
        code="eg",
        name="Egypt",
        host="www.jumia.com.eg",
        currency="EGP",
        currency_symbols=("EGP", "ج.م", "E£"),
        tld="com.eg",
    ),
    "gh": Country(
        code="gh",
        name="Ghana",
        host="www.jumia.com.gh",
        currency="GHS",
        currency_symbols=("GH₵", "GHS", "GH¢", "GHc"),
        tld="com.gh",
    ),
    "ci": Country(
        code="ci",
        name="Ivory Coast",
        host="www.jumia.ci",
        currency="XOF",
        currency_symbols=("CFA", "FCFA", "XOF"),
        tld="ci",
    ),
    "ke": Country(
        code="ke",
        name="Kenya",
        host="www.jumia.co.ke",
        currency="KES",
        currency_symbols=("KSh", "KES", "Ksh", "KSH"),
        tld="co.ke",
    ),
    "ma": Country(
        code="ma",
        name="Morocco",
        host="www.jumia.ma",
        currency="MAD",
        currency_symbols=("MAD", "Dhs", "DH", "د.م."),
        tld="ma",
    ),
    "ng": Country(
        code="ng",
        name="Nigeria",
        host="www.jumia.com.ng",
        currency="NGN",
        currency_symbols=("₦", "NGN", "Naira"),
        tld="com.ng",
    ),
    "sn": Country(
        code="sn",
        name="Senegal",
        host="www.jumia.sn",
        currency="XOF",
        currency_symbols=("CFA", "FCFA", "XOF"),
        tld="sn",
    ),
    "ug": Country(
        code="ug",
        name="Uganda",
        host="www.jumia.ug",
        currency="UGX",
        currency_symbols=("UGX", "USh", "Ush", "Sh"),
        tld="ug",
    ),
}

# Host (with and without www) → country code
HOST_TO_CODE: dict[str, str] = {}
for _country in COUNTRIES.values():
    HOST_TO_CODE[_country.host] = _country.code
    HOST_TO_CODE[_country.host.removeprefix("www.")] = _country.code

JUMIA_HOSTS = tuple(sorted(HOST_TO_CODE.keys()))

ALERT_MODES = ("price_up", "price_down", "any_change")


def country_from_host(host: str) -> Optional[Country]:
    host = (host or "").lower().strip()
    if host.startswith("www."):
        key = host
        alt = host[4:]
    else:
        key = host
        alt = f"www.{host}"
    code = HOST_TO_CODE.get(key) or HOST_TO_CODE.get(alt)
    return COUNTRIES.get(code) if code else None


def country_from_url(url: str) -> Optional[Country]:
    try:
        parsed = urlparse(url)
    except Exception:
        return None
    return country_from_host(parsed.netloc)


def canonicalize_product_url(url: str) -> str:
    """Normalize a Jumia product URL: https, www host, no query/fragment."""
    raw = (url or "").strip()
    if raw.startswith("//"):
        raw = "https:" + raw
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw
    parsed = urlparse(raw)
    host = parsed.netloc.lower()
    if host.startswith("jumia."):
        host = "www." + host
    path = parsed.path.rstrip("/") or "/"
    return urlunparse(("https", host, path, "", "", ""))


def is_jumia_product_url(url: str) -> bool:
    country = country_from_url(url)
    if country is None:
        return False
    path = urlparse(url).path.lower()
    # Jumia PDP URLs almost always end in .html
    return path.endswith(".html")


def countries_payload() -> list[dict]:
    return [
        {
            "code": c.code,
            "name": c.name,
            "host": c.host,
            "currency": c.currency,
            "origin": f"https://{c.host}",
        }
        for c in COUNTRIES.values()
    ]
