from shared.countries import (
    COUNTRIES,
    canonicalize_product_url,
    country_from_url,
    is_jumia_product_url,
)
from tests.html_samples import SAMPLE_URLS


def test_all_eight_countries_mapped():
    assert set(COUNTRIES) == {"eg", "gh", "ci", "ke", "ma", "ng", "sn", "ug"}
    assert COUNTRIES["eg"].host == "www.jumia.com.eg"
    assert COUNTRIES["gh"].host == "www.jumia.com.gh"
    assert COUNTRIES["ci"].host == "www.jumia.ci"
    assert COUNTRIES["ke"].host == "www.jumia.co.ke"
    assert COUNTRIES["ma"].host == "www.jumia.ma"
    assert COUNTRIES["ng"].host == "www.jumia.com.ng"
    assert COUNTRIES["sn"].host == "www.jumia.sn"
    assert COUNTRIES["ug"].host == "www.jumia.ug"


def test_country_from_url_with_and_without_www():
    assert country_from_url("https://jumia.co.ke/foo.html").code == "ke"
    assert country_from_url("https://www.jumia.com.ng/foo.html").code == "ng"
    assert country_from_url("https://example.com/x") is None


def test_sample_urls_cover_every_market():
    for code, url in SAMPLE_URLS.items():
        country = country_from_url(url)
        assert country is not None
        assert country.code == code
        assert is_jumia_product_url(url)


def test_canonicalize_strips_tracking():
    url = canonicalize_product_url("http://jumia.co.ke/phone.html?sid=abc#hash")
    assert url == "https://www.jumia.co.ke/phone.html"
