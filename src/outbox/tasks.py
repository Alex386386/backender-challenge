import json

import structlog
from celery import Task, shared_task
from sentry_sdk import capture_exception

from core import settings
from core.event_log_client import EventLogClient
from outbox.models import EventOutbox

logger = structlog.get_logger(__name__)


@shared_task(bind=True)
def process_outbox_events(self: Task) -> None:
    """Обрабатывает и отправляет события из Outbox в ClickHouse."""
    events = list(
        EventOutbox.objects.filter(processed=False)[: settings.CELERY_OBJECTS_AMOUNT],
    )
    if not events:
        return

    event_data = [
        {
            "event_id": event.id,
            "event_type": event.event_type,
            "event_date_time": event.event_date_time.isoformat(),
            "environment": event.environment,
            "event_context": json.dumps(event.event_context),
            "metadata_version": event.metadata_version,
            "processed": True,
        }
        for event in events
    ]

    try:
        with EventLogClient.init() as client:
            client.insert_from_outbox(event_data)
    except Exception as e:
        capture_exception(e)
        logger.error("Retrying due to failure", error=str(e))
        self.retry(countdown=10, max_retries=5, exc=e)


@shared_task(bind=True)
def cleanup_processed_outbox_events(self: Task) -> None:
    """Удаляет обработанные события из Outbox."""
    try:
        deleted_count, _ = EventOutbox.objects.filter(processed=True).delete()
        logger.info(f"Deleted {deleted_count} processed events from Outbox")
    except Exception as e:
        capture_exception(e)
        logger.error("Retrying due to failure", error=str(e))
        self.retry(countdown=10, max_retries=5, exc=e)
