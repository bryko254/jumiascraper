"""Poll watched Jumia product URLs and publish scrape results to RabbitMQ."""

from __future__ import annotations

import json
import logging
import os
import random
import time
from typing import Optional

import pika
import redis
import requests
from dotenv import load_dotenv
from sqlalchemy.orm import Session, joinedload

from shared.database import make_engine, make_session_factory, wait_for_db
from shared.models import Watch
from shared.parser import parse_product_html

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("scraper")

QUEUE_NAME = os.getenv("PRODUCT_QUEUE", "product_queue")
SCRAPE_INTERVAL = int(os.getenv("SCRAPE_INTERVAL_SECONDS", "900"))
CYCLE_SLEEP = int(os.getenv("SCRAPE_CYCLE_SECONDS", "30"))
POLITE_MIN = float(os.getenv("SCRAPE_POLITE_MIN_SECONDS", "2"))
POLITE_MAX = float(os.getenv("SCRAPE_POLITE_MAX_SECONDS", "5"))
REQUEST_TIMEOUT = int(os.getenv("SCRAPE_TIMEOUT_SECONDS", "20"))


def get_headers() -> dict:
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    ]
    return {
        "User-Agent": random.choice(user_agents),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en,fr;q=0.8",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }


def connect_rabbitmq():
    credentials = pika.PlainCredentials(
        os.getenv("RABBITMQ_USER", "guest"),
        os.getenv("RABBITMQ_PASSWORD", "guest"),
    )
    parameters = pika.ConnectionParameters(
        host=os.getenv("RABBITMQ_HOST", "rabbitmq"),
        port=int(os.getenv("RABBITMQ_PORT", "5672")),
        credentials=credentials,
        heartbeat=600,
        blocked_connection_timeout=300,
    )
    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()
    channel.queue_declare(queue=QUEUE_NAME, durable=True)
    channel.confirm_delivery()
    logger.info("Connected to RabbitMQ")
    return connection, channel


def connect_redis() -> Optional[redis.Redis]:
    try:
        client = redis.Redis(
            host=os.getenv("REDIS_HOST", "redis"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            db=0,
            decode_responses=True,
        )
        client.ping()
        logger.info("Connected to Redis")
        return client
    except Exception as exc:
        logger.warning("Redis unavailable, continuing without cache: %s", exc)
        return None


def recently_scraped(cache: Optional[redis.Redis], url: str) -> bool:
    if cache is None:
        return False
    try:
        return bool(cache.get(f"scrape:{url}"))
    except Exception:
        return False


def mark_scraped(cache: Optional[redis.Redis], url: str) -> None:
    if cache is None:
        return
    try:
        cache.setex(f"scrape:{url}", SCRAPE_INTERVAL, "1")
    except Exception as exc:
        logger.warning("Redis setex failed: %s", exc)


def fetch_html(url: str) -> Optional[str]:
    try:
        response = requests.get(url, headers=get_headers(), timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.text
    except requests.RequestException as exc:
        logger.error("HTTP error fetching %s: %s", url, exc)
        return None


def publish_result(channel, payload: dict) -> None:
    channel.basic_publish(
        exchange="",
        routing_key=QUEUE_NAME,
        body=json.dumps(payload),
        properties=pika.BasicProperties(
            delivery_mode=2,
            content_type="application/json",
        ),
    )


def active_watch_urls(db: Session) -> list[str]:
    rows = (
        db.query(Watch)
        .options(joinedload(Watch.product))
        .filter(Watch.is_active.is_(True))
        .all()
    )
    urls = []
    seen = set()
    for watch in rows:
        url = watch.product.product_url if watch.product else None
        if url and url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def scrape_one(url: str) -> Optional[dict]:
    html = fetch_html(url)
    if not html:
        return None
    return parse_product_html(html, url)


def main() -> None:
    logger.info("Starting watch-based scraper (interval=%ss)", SCRAPE_INTERVAL)
    engine = make_engine()
    wait_for_db(engine)
    SessionLocal = make_session_factory(engine)
    cache = connect_redis()

    connection = None
    channel = None

    while True:
        try:
            if connection is None or connection.is_closed:
                connection, channel = connect_rabbitmq()

            db = SessionLocal()
            try:
                urls = active_watch_urls(db)
            finally:
                db.close()

            if not urls:
                logger.info("No active watches; sleeping %ss", CYCLE_SLEEP)
                time.sleep(CYCLE_SLEEP)
                continue

            logger.info("Scraping %s watched product(s)", len(urls))
            for url in urls:
                if recently_scraped(cache, url):
                    logger.info("Skip (cached): %s", url)
                    continue
                payload = scrape_one(url)
                if payload:
                    publish_result(channel, payload)
                    mark_scraped(cache, url)
                    logger.info("Queued scrape result for %s (price=%s)", url, payload.get("price"))
                else:
                    logger.warning("No parseable product at %s", url)
                time.sleep(random.uniform(POLITE_MIN, POLITE_MAX))

            time.sleep(CYCLE_SLEEP)
        except KeyboardInterrupt:
            logger.info("Scraper stopped")
            break
        except Exception:
            logger.exception("Scraper cycle failed; retrying")
            connection = None
            channel = None
            time.sleep(5)

    if connection and not connection.is_closed:
        connection.close()


if __name__ == "__main__":
    time.sleep(int(os.getenv("STARTUP_DELAY_SECONDS", "5")))
    main()
