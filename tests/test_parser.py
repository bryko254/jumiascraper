from shared.parser import parse_product_html
from tests.html_samples import SAMPLE_URLS, html_for_country, load_fixture


def test_parse_kenya_jsonld_fixture():
    parsed = parse_product_html(
        load_fixture("product_ke.html"),
        "https://www.jumia.co.ke/infinix-smart-8-64gb.html",
    )
    assert parsed is not None
    assert parsed["name"] == "Infinix Smart 8 64GB"
    assert parsed["price"] == 11200.0
    assert parsed["currency"] == "KES"
    assert parsed["country"] == "ke"
    assert parsed["old_price"] == 15000.0
    assert parsed["image_url"]


def test_parse_kenya_price_drop_fixture():
    parsed = parse_product_html(
        load_fixture("product_ke_drop.html"),
        "https://www.jumia.co.ke/infinix-smart-8-64gb.html",
    )
    assert parsed["price"] == 9800.0


def test_parse_nigeria_fixture():
    parsed = parse_product_html(
        load_fixture("product_ng.html"),
        "https://www.jumia.com.ng/tecno-spark-20.html",
    )
    assert parsed["country"] == "ng"
    assert parsed["price"] == 125000.0
    assert parsed["currency"] == "NGN"


def test_parse_css_fallback_without_jsonld():
    parsed = parse_product_html(
        load_fixture("product_ke_css_only.html"),
        "https://www.jumia.co.ke/samsung-galaxy-a05.html",
    )
    assert parsed is not None
    assert parsed["name"] == "Samsung Galaxy A05"
    assert parsed["price"] == 14499.0


def test_parse_generated_html_all_countries():
    for code, url in SAMPLE_URLS.items():
        parsed = parse_product_html(html_for_country(code), url)
        assert parsed is not None, code
        assert parsed["country"] == code
        assert parsed["price"] > 0
