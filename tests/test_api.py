from tests.html_samples import SAMPLE_URLS, html_for_country, load_fixture

KE_URL = "https://www.jumia.co.ke/infinix-smart-8-64gb.html"


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["database"] == "connected"


def test_countries_endpoint_lists_eight(client):
    response = client.get("/countries")
    assert response.status_code == 200
    codes = {row["code"] for row in response.json()}
    assert codes == {"eg", "gh", "ci", "ke", "ma", "ng", "sn", "ug"}


def test_watch_crud(client):
    created = client.post(
        "/watches",
        json={"product_url": KE_URL, "alert_mode": "price_down", "name": "Infinix Smart 8"},
    )
    assert created.status_code == 201
    watch = created.json()
    assert watch["alert_mode"] == "price_down"
    assert watch["product"]["country"] == "ke"
    watch_id = watch["id"]
    product_id = watch["product"]["id"]

    listed = client.get("/watches").json()
    assert len(listed) == 1

    product = client.get(f"/products/{product_id}").json()
    assert product["product_url"].endswith("/infinix-smart-8-64gb.html")

    deleted = client.delete(f"/watches/{watch_id}")
    assert deleted.status_code == 204
    assert client.get("/watches").json() == []


def test_rejects_non_jumia_url(client):
    response = client.post("/watches", json={"product_url": "https://example.com/x.html"})
    assert response.status_code == 422


def test_watch_then_fixture_price_drop_creates_alert(client, ingest_headers):
    """End-to-end smoke: watch → mock scrape → price drop → in-API alert."""
    watch = client.post(
        "/watches",
        json={"product_url": KE_URL, "alert_mode": "price_down", "name": "Infinix Smart 8"},
    ).json()
    product_id = watch["product"]["id"]

    first = client.post(
        "/internal/ingest",
        headers=ingest_headers,
        json={"product_url": KE_URL, "html": load_fixture("product_ke.html")},
    )
    assert first.status_code == 200
    assert first.json()["first_observation"] is True
    assert first.json()["alerts_created"] == 0

    product = client.get(f"/products/{product_id}").json()
    assert product["current_price"] == 11200.0

    second = client.post(
        "/internal/ingest",
        headers=ingest_headers,
        json={"product_url": KE_URL, "html": load_fixture("product_ke_drop.html")},
    )
    assert second.status_code == 200
    assert second.json()["price_changed"] is True
    assert second.json()["direction"] == "down"
    assert second.json()["alerts_created"] == 1

    alerts = client.get("/alerts").json()
    assert len(alerts) == 1
    assert alerts[0]["direction"] == "down"
    assert alerts[0]["old_price"] == 11200.0
    assert alerts[0]["new_price"] == 9800.0
    assert alerts[0]["delivery_status"] == "stubbed"

    history = client.get(f"/products/{product_id}/history").json()
    assert [row["price"] for row in history] == [9800.0, 11200.0]


def test_ingest_requires_token(client):
    response = client.post(
        "/internal/ingest",
        json={"product_url": KE_URL, "price": 1, "name": "x", "country": "ke"},
    )
    assert response.status_code == 401


def test_multi_country_watches_and_alerts(client, ingest_headers):
    for code, url in SAMPLE_URLS.items():
        response = client.post(
            "/watches",
            json={"product_url": url, "alert_mode": "any_change", "name": f"{code} phone"},
        )
        assert response.status_code == 201, response.text
        ingest = client.post(
            "/internal/ingest",
            headers=ingest_headers,
            json={"product_url": url, "html": html_for_country(code)},
        )
        assert ingest.status_code == 200
        drop = client.post(
            "/internal/ingest",
            headers=ingest_headers,
            json={"product_url": url, "html": html_for_country(code, price_override=100)},
        )
        assert drop.status_code == 200
        assert drop.json()["alerts_created"] == 1

    products = client.get("/products").json()
    assert len(products) == 8
    countries = {p["country"] for p in products}
    assert countries == set(SAMPLE_URLS)
    assert len(client.get("/alerts").json()) == 8
    kenya_only = client.get("/products?country=ke").json()
    assert len(kenya_only) == 1
