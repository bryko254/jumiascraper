"""Currency-agnostic price parsing for the eight Jumia markets."""

from __future__ import annotations

import re
from typing import Optional

from shared.countries import COUNTRIES, Country, country_from_url

# Longest tokens first so "KSh" wins over "Sh", "FCFA" over "CFA", etc.
_SYMBOL_PARTS = sorted(
    {sym for c in COUNTRIES.values() for sym in c.currency_symbols},
    key=len,
    reverse=True,
)
_SYMBOL_RE = re.compile(
    r"(?:GH₵|GH¢|₦|ج\.م\.?|د\.م\.?|"
    + "|".join(re.escape(s) for s in _SYMBOL_PARTS)
    + r")",
    re.IGNORECASE,
)
_NBSP_RE = re.compile(r"[\u00a0\u202f\u2009]")
_WS_RE = re.compile(r"\s+")


def parse_price(text: Optional[str], country: Optional[Country] = None) -> Optional[float]:
    """Parse a displayed Jumia price into a float, or None if unusable."""
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return float(text)

    raw = _NBSP_RE.sub(" ", str(text)).strip()
    if not raw:
        return None

    if country:
        for symbol in sorted(country.currency_symbols, key=len, reverse=True):
            raw = re.sub(re.escape(symbol), "", raw, flags=re.IGNORECASE)
    raw = _SYMBOL_RE.sub("", raw)
    raw = raw.replace("£", "").replace("$", "")
    raw = _WS_RE.sub("", raw)
    raw = re.sub(r"[^\d,.\-]", "", raw)
    if raw in {"", "-", ".", ",", "-.", "-,"}:
        return None

    negative = raw.startswith("-")
    raw = raw.lstrip("-")

    if "," in raw and "." in raw:
        # The last separator is the decimal mark.
        if raw.rfind(",") > raw.rfind("."):
            raw = raw.replace(".", "").replace(",", ".")
        else:
            raw = raw.replace(",", "")
    elif "," in raw:
        parts = raw.split(",")
        if len(parts[-1]) == 3 and len(parts) > 1:
            # Thousands grouping: 1,234 or 1,234,567
            raw = raw.replace(",", "")
        else:
            raw = raw.replace(",", ".")
    elif "." in raw:
        parts = raw.split(".")
        if len(parts) > 2:
            raw = raw.replace(".", "")
        elif len(parts) == 2 and len(parts[1]) == 3 and len(parts[0]) <= 3:
            # Ambiguous 12.500 — treat as thousands for CFA-style markets.
            if country and country.currency == "XOF":
                raw = raw.replace(".", "")

    try:
        value = float(raw)
    except ValueError:
        return None
    if negative:
        value = -value
    if value < 0:
        return None
    return value


def parse_price_for_url(text: Optional[str], url: str) -> Optional[float]:
    return parse_price(text, country_from_url(url))
