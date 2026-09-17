"""RabbitMQ connection helpers (scraper + processor only)."""

from __future__ import annotations

import pika

from shared.settings import rabbitmq_url


def rabbitmq_parameters() -> pika.URLParameters:
    params = pika.URLParameters(rabbitmq_url())
    params.heartbeat = 600
    params.blocked_connection_timeout = 300
    return params
