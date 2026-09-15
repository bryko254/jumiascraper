import json
from pathlib import Path

from shared.countries import COUNTRIES

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def product_html(
    *,
    name: str,
    price: str | float,
    currency: str,
    display_price: str | None = None,
    image: str = "https://example.test/p.jpg",
    sku: str = "SKU-1",
) -> str:
    payload = {
        "@context": "https://schema.org/",
        "@type": "Product",
        "name": name,
        "image": image,
        "sku": sku,
        "offers": {"@type": "Offer", "priceCurrency": currency, "price": str(price)},
    }
    shown = display_price or str(price)
    return f"""<!DOCTYPE html>
<html><head>
<script type="application/ld+json">{json.dumps(payload)}</script>
</head>
<body>
<h1>{name}</h1>
<span class="-b -fs24">{shown}</span>
</body></html>
"""


SAMPLE_URLS = {
    "eg": "https://www.jumia.com.eg/generic-phone-eg.html",
    "gh": "https://www.jumia.com.gh/generic-phone-gh.html",
    "ci": "https://www.jumia.ci/generic-phone-ci.html",
    "ke": "https://www.jumia.co.ke/generic-phone-ke.html",
    "ma": "https://www.jumia.ma/generic-phone-ma.html",
    "ng": "https://www.jumia.com.ng/generic-phone-ng.html",
    "sn": "https://www.jumia.sn/generic-phone-sn.html",
    "ug": "https://www.jumia.ug/generic-phone-ug.html",
}

SAMPLE_PRICES = {
    "eg": ("EGP", "4,499", 4499.0),
    "gh": ("GHS", "GH₵ 1,250", 1250.0),
    "ci": ("XOF", "85 000 CFA", 85000.0),
    "ke": ("KES", "KSh 11,200", 11200.0),
    "ma": ("MAD", "Dhs 899", 899.0),
    "ng": ("NGN", "₦ 125,000", 125000.0),
    "sn": ("XOF", "79.000 CFA", 79000.0),
    "ug": ("UGX", "USh 450,000", 450000.0),
}


def html_for_country(code: str, price_override: float | None = None) -> str:
    country = COUNTRIES[code]
    currency, display, numeric = SAMPLE_PRICES[code]
    value = price_override if price_override is not None else numeric
    return product_html(
        name=f"Demo phone {country.name}",
        price=value,
        currency=country.currency,
        display_price=display if price_override is None else str(value),
    )
