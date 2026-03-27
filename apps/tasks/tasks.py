import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def log_worker_heartbeat() -> None:
    logger.info("Celery heartbeat test message")
