from celery import Celery
from app.core.config import settings
import asyncio
import sys

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

celery_app = Celery("codedocs_worker")
celery_app.conf.broker_url = settings.redis_url
celery_app.conf.result_backend = settings.redis_url

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    broker_connection_retry_on_startup=True,
    worker_cancel_long_running_tasks_on_connection_loss=True,
)

celery_app.autodiscover_tasks(["app.workers"])
