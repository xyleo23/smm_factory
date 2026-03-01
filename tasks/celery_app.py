"""Celery application configuration for SMM Factory."""

from celery import Celery
from loguru import logger

from core.config import config


# Initialize Celery app
celery_app = Celery(
    "smm_factory",
    broker=config.redis_url,
    backend=config.redis_url,
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Moscow",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    result_expires=3600,
    broker_connection_retry_on_startup=True,
)

# Auto-discover tasks from tasks module
celery_app.autodiscover_tasks(["tasks"])

logger.info("Celery app initialized with broker: {}", config.redis_url)
