import json
import re
from collections.abc import Generator
from contextlib import contextmanager
from datetime import timedelta

import clickhouse_connect
import structlog
from clickhouse_connect.driver.exceptions import DatabaseError
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from sentry_sdk import capture_exception

from core.base_model import Model
from outbox.models import EventOutbox

logger = structlog.get_logger(__name__)

EVENT_LOG_COLUMNS = [
    "event_type",
    "event_date_time",
    "environment",
    "event_context",
]


class EventLogClient:
    def __init__(self, client: clickhouse_connect.driver.Client) -> None:
        self._client = client

    @classmethod
    @contextmanager
    def init(cls) -> Generator["EventLogClient"]:
        client = clickhouse_connect.get_client(
            host=settings.CLICKHOUSE_HOST,
            port=settings.CLICKHOUSE_PORT,
            user=settings.CLICKHOUSE_USER,
            password=settings.CLICKHOUSE_PASSWORD,
            query_retries=2,
            connect_timeout=30,
            send_receive_timeout=10,
        )
        try:
            yield cls(client)
        except Exception as e:
            capture_exception(e)
            logger.error("error while executing clickhouse query", error=str(e))
        finally:
            client.close()

    def insert_from_outbox(self, data: list[Model]) -> None:
        """Вставляет события из EventOutbox в ClickHouse."""
        if not data:
            return

        try:
            with transaction.atomic():
                self._client.insert(
                    database=settings.CLICKHOUSE_SCHEMA,
                    table=settings.CLICKHOUSE_EVENT_LOG_TABLE_NAME,
                    column_names=EVENT_LOG_COLUMNS,
                    data=self._convert_data(data),
                )
                logger.info(
                    "Events successfully inserted into ClickHouse",
                    count=len(data),
                )

                EventOutbox.objects.filter(
                    id__in=[event["event_id"] for event in data],
                ).update(processed=True)
                logger.info("Events processed status change to True:", count=len(data))
        except DatabaseError as e:
            capture_exception(e)
            logger.error("Failed to insert events into ClickHouse", error=str(e))
            raise
        except Exception as e:
            capture_exception(e)
            logger.error("Transaction failed, rolling back changes", error=str(e))
            self.delete_inserted_data()
            raise

    def delete_inserted_data(self) -> None:
        current_time = timezone.now()
        current_time_without_tz = current_time.replace(tzinfo=None)
        time_60_seconds_ago = (current_time - timedelta(seconds=60)).replace(
            tzinfo=None,
        )

        delete_query = f"""
            ALTER TABLE {settings.CLICKHOUSE_EVENT_LOG_TABLE_NAME}
            DELETE WHERE event_date_time >= '{time_60_seconds_ago.isoformat()}'
            AND event_date_time <= '{current_time_without_tz.isoformat()}';
        """
        try:
            self._client.query(delete_query)

            logger.info(f"Executing ClickHouse DELETE query: {delete_query}")
            self._client.query(delete_query)

            logger.info("Removed events from ClickHouse after failure")
        except Exception as e:
            capture_exception(e)
            logger.error(
                "Failed to remove events from ClickHouse",
                error={"error": str(e), "query": delete_query},
            )
            raise

    def _convert_data(self, data: list[Model]) -> list[tuple]:
        return [
            (
                self._to_snake_case(event.__class__.__name__),
                timezone.now(),
                settings.ENVIRONMENT,
                json.dumps(event),
            )
            for event in data
        ]

    @staticmethod
    def _to_snake_case(event_name: str) -> str:
        result = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", event_name)
        return re.sub("([a-z0-9])([A-Z])", r"\1_\2", result).lower()
