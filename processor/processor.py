"""Consume scrape results, upsert products, and create in-API alerts."""

from __future__ import annotations

import json
import logging
import os
import threading
import time

import pika
from dotenv import load_dotenv
from sqlalchemy import text

from shared.database import init_db, make_engine, make_session_factory, wait_for_db
from shared.monitor import apply_scrape_result
from shared.queue import rabbitmq_parameters
from shared.retention import apply_history_retention
from shared.settings import history_retention_days, history_retention_interval_seconds

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("processor")

QUEUE_NAME = os.getenv("PRODUCT_QUEUE", "product_queue")

engine = make_engine()
SessionLocal = make_session_factory(engine)


def process_message(ch, method, _properties, body):
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        payload = json.loads(body)
        logger.info("Received scrape result for %s", payload.get("product_url"))
        summary = apply_scrape_result(db, payload)
        db.commit()
        ch.basic_ack(delivery_tag=method.delivery_tag)
        logger.info("Processed: %s", summary)
    except Exception:
        logger.exception("Failed to process message")
        db.rollback()
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        time.sleep(1)
    finally:
        db.close()


def run_retention_once() -> None:
    db = SessionLocal()
    try:
        summary = apply_history_retention(db)
        db.commit()
        logger.info("Retention pass: %s", summary)
    except Exception:
        logger.exception("History retention failed")
        db.rollback()
    finally:
        db.close()


def retention_loop() -> None:
    interval = history_retention_interval_seconds()
    logger.info(
        "History retention thread started (raw window=%s days, every %ss)",
        history_retention_days(),
        interval,
    )
    while True:
        time.sleep(interval)
        run_retention_once()


def main() -> None:
    wait_for_db(engine)
    init_db(engine)
    logger.info("Processor starting")
    run_retention_once()
    threading.Thread(target=retention_loop, name="history-retention", daemon=True).start()

    while True:
        try:
            connection = pika.BlockingConnection(rabbitmq_parameters())
            channel = connection.channel()
            channel.queue_declare(queue=QUEUE_NAME, durable=True)
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue=QUEUE_NAME, on_message_callback=process_message, auto_ack=False)
            logger.info("Consuming %s", QUEUE_NAME)
            channel.start_consuming()
        except pika.exceptions.AMQPConnectionError as exc:
            logger.error("RabbitMQ connection error: %s", exc)
            time.sleep(5)
        except Exception:
            logger.exception("Processor crashed; retrying")
            time.sleep(5)


if __name__ == "__main__":
    time.sleep(int(os.getenv("STARTUP_DELAY_SECONDS", "5")))
    main()
