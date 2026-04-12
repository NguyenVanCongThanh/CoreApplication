from __future__ import annotations

import logging
from celery import Celery
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# DEPRECATED: Celery is being decommissioned in favor of Kafka.
# All indexing and graph maintenance tasks have been migrated to app.worker.kafka_worker.
celery_app = Celery(
    "ai_worker_deprecated",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

@celery_app.task(name="tasks.deprecated_placeholder")
def deprecated_placeholder():
    logger.warning("Triggered a deprecated Celery task. Please use Kafka events instead.")