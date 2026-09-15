# Jumia Price Monitor

Chrome extension (UI only) + serverside scraper/monitor/alerts for Jumia product prices.

Supported storefronts:

| Country | Domain | Currency |
| --- | --- | --- |
| Egypt | `www.jumia.com.eg` | EGP |
| Ghana | `www.jumia.com.gh` | GHS |
| Ivory Coast | `www.jumia.ci` | XOF |
| Kenya | `www.jumia.co.ke` | KES |
| Morocco | `www.jumia.ma` | MAD |
| Nigeria | `www.jumia.com.ng` | NGN |
| Senegal | `www.jumia.sn` | XOF |
| Uganda | `www.jumia.ug` | UGX |

The extension never scrapes. It calls this API. The scraper fetches **watched product URLs** (not a Kenya-only category crawl), the processor upserts by `product_url`, writes price history on first sight / change, and creates **in-API alerts**. Email and webhook delivery are logged stubs (`ALERT_EMAIL_TO`, `ALERT_WEBHOOK_URL`).

```
Chrome extension  --REST-->  FastAPI
                                |
                          PostgreSQL
                                ^
scraper (BS4) --RabbitMQ--> processor
     |                          |
   Redis TTL cache         upsert + alerts
```

## Quick start (server)

```bash
cp .env.example .env   # optional; defaults match .env.example
docker compose up --build
```

API: [http://127.0.0.1:8001](http://127.0.0.1:8001)  
Swagger: [http://127.0.0.1:8001/docs](http://127.0.0.1:8001/docs)  
Health: [http://127.0.0.1:8001/health](http://127.0.0.1:8001/health)  
RabbitMQ UI: [http://127.0.0.1:15673](http://127.0.0.1:15673) (guest/guest from `.env.example`)

Host ports are remapped to avoid common local clashes: Postgres `5433`, Redis `6380`, RabbitMQ `5673`/`15673`, API `8001`.

If you previously ran the legacy Kenya-only stack, reset the Postgres volume so the unified schema can be created:

```bash
docker compose down -v
docker compose up --build
```

With **no watches**, the scraper idles and does not hit Jumia. After you add a watch it will HTTP-GET that product page on `SCRAPE_INTERVAL_SECONDS` (default 15 minutes).

## Load the Chrome extension (unpacked)

1. Start the API (`docker compose up`).
2. Open `chrome://extensions`, enable **Developer mode**.
3. **Load unpacked** and select the `extension/` folder in this repo.
4. Open the extension **Settings** (or right-click the icon → Options) and set API base URL to `http://127.0.0.1:8001` if it is not already.
5. Visit a Jumia product page (URL ending in `.html`) in any of the 8 countries.
6. Choose alert mode (**price up** / **price down** / **any change**) and click **Watch this product**.
7. Watches and recent alerts appear in the popup. Unread alerts also show as a badge.

## API (extension-facing)

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | DB health + counts |
| GET | `/countries` | Eight markets |
| POST | `/watches` | Watch a product URL (`alert_mode`: `price_up` \| `price_down` \| `any_change`) |
| GET | `/watches` | List watches |
| DELETE | `/watches/{id}` | Remove a watch |
| GET | `/products` | List products (`?country=ke`) |
| GET | `/products/{id}` | Product detail |
| GET | `/products/{id}/history` | Price history |
| GET | `/alerts` | Recent alerts (`?unread_only=true`) |
| PATCH | `/alerts/{id}` | `{ "read": true }` |
| POST | `/internal/ingest` | Fixture ingest (header `X-Ingest-Token`) |

Create-watch body:

```json
{
  "product_url": "https://www.jumia.co.ke/some-product.html",
  "alert_mode": "price_down",
  "name": "optional label from the page"
}
```

Demo a price drop without Jumia (token from `.env`):

```bash
curl -s -X POST http://127.0.0.1:8001/watches \
  -H 'Content-Type: application/json' \
  -d '{"product_url":"https://www.jumia.co.ke/infinix-smart-8-64gb.html","alert_mode":"price_down","name":"Infinix Smart 8"}'

curl -s -X POST http://127.0.0.1:8001/internal/ingest \
  -H 'Content-Type: application/json' \
  -H 'X-Ingest-Token: dev-ingest-token' \
  -d '{"product_url":"https://www.jumia.co.ke/infinix-smart-8-64gb.html","name":"Infinix Smart 8","price":11200,"currency":"KES","country":"ke"}'

curl -s -X POST http://127.0.0.1:8001/internal/ingest \
  -H 'Content-Type: application/json' \
  -H 'X-Ingest-Token: dev-ingest-token' \
  -d '{"product_url":"https://www.jumia.co.ke/infinix-smart-8-64gb.html","name":"Infinix Smart 8","price":9800,"currency":"KES","country":"ke"}'

curl -s http://127.0.0.1:8001/alerts
```

Set `ENABLE_INGEST=false` if you do not want the ingest endpoint.

## Tests (fixtures, no live Jumia)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q
python scripts/smoke_test.py
```

The smoke path is **watch → ingest first price → ingest lower price → alert**. HTML fixtures live in `tests/fixtures/`.

## Layout

```
shared/       models, countries, price parser, HTML parser, alert logic
api/          FastAPI
scraper/      polls watches, fetches product pages, publishes JSON
processor/    consumes queue, upserts, writes history + alerts
extension/    Manifest V3 popup / options / content script
tests/        pytest + HTML fixtures
```

Schema uses `products.current_price` (not a separate `price` column), unique `product_url`, and upserts on every scrape. Watches are unique per `(product, alert_mode)`.

Selectors try JSON-LD `Product` / `Offer` first, then Open Graph, then Jumia CSS (`h1`, `span.-b.-fs24`, `.prc`). Currency parsing is not Kenya/`KSh`-only.

## Notes

- Copy `.env.example` to `.env`. Do not commit real credentials.
- Category-wide Kenya crawling from the legacy scraper is gone; monitoring is watch-driven and multi-country.
- Email/webhook are stubs so you can still see every alert via `GET /alerts` and the extension.
