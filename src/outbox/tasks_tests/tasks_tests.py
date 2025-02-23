from unittest.mock import patch

import pytest
from clickhouse_connect.driver import Client
from clickhouse_connect.driver.query import QueryResult
from django.conf import settings
from django.db.models import QuerySet

from outbox.models import EventOutbox
from outbox.tasks import process_outbox_events, cleanup_processed_outbox_events
from outbox.tasks_tests.tasks_test_utils import check_in_result

pytestmark = [pytest.mark.django_db]


@pytest.fixture()
def create_outbox_event():
    """Фикстура для создания события в Outbox."""
    event = EventOutbox.objects.create(
        event_type="user_created",
        event_context={
            "email": "test@email.com",
            "first_name": "Test",
            "last_name": "Testovich",
        },
        processed=False,
        environment="local",
        metadata_version=1,
    )
    return event


@pytest.fixture(scope="function", autouse=True)
def clear_clickhouse_event_log(f_ch_client):
    """Очистка таблицы event_log в ClickHouse перед каждым тестом."""
    delete_query = f"TRUNCATE TABLE {settings.CLICKHOUSE_SCHEMA}.{settings.CLICKHOUSE_EVENT_LOG_TABLE_NAME}"
    f_ch_client.query(delete_query)
    yield


def test_process_outbox_events_success(create_outbox_event, f_ch_client: Client):
    """Тест успешной обработки события из Outbox."""
    event_id: int = create_outbox_event.id
    process_outbox_events.apply()
    event = EventOutbox.objects.get(id=event_id)
    assert event.processed is True
    log: QueryResult = f_ch_client.query(
        f"SELECT * FROM {settings.CLICKHOUSE_SCHEMA}.{settings.CLICKHOUSE_EVENT_LOG_TABLE_NAME}"
    )
    found_event = check_in_result(event_id, log)
    assert found_event, f"Event with id {event_id} was not found in the ClickHouse log"


def test_process_outbox_events_failure(
    create_outbox_event, f_ch_client, clear_clickhouse_event_log
):
    """Тест обработки сбоя: при ошибке в update данные удаляются из Clickhouse."""
    event_id: int = create_outbox_event.id
    with patch.object(
        QuerySet, "update", side_effect=RuntimeError("Error on update status processed")
    ):
        process_outbox_events.apply()
    event = EventOutbox.objects.get(id=event_id)
    assert event.processed is False
    log: QueryResult = f_ch_client.query(
        f"SELECT * FROM {settings.CLICKHOUSE_SCHEMA}.{settings.CLICKHOUSE_EVENT_LOG_TABLE_NAME}"
    )
    found_event = check_in_result(event_id, log)
    assert (
        not found_event
    ), f"Event with id {event_id} should not be in the ClickHouse log"


def test_no_events_to_process(f_ch_client: Client):
    """Тест, если нет событий для обработки."""
    process_outbox_events.apply()
    assert EventOutbox.objects.count() == 0
    log: QueryResult = f_ch_client.query(
        f"SELECT * FROM {settings.CLICKHOUSE_SCHEMA}.{settings.CLICKHOUSE_EVENT_LOG_TABLE_NAME}"
    )
    assert len(log.result_rows) == 0


def test_cleanup_processed_outbox_events_success(create_outbox_event):
    """Тест успешного удаления обработанных событий."""
    assert EventOutbox.objects.count() == 1
    create_outbox_event.processed = True
    create_outbox_event.save()
    cleanup_processed_outbox_events.apply()
    assert EventOutbox.objects.count() == 0


def test_cleanup_processed_outbox_events_no_processed_events():
    """Тест, если нет обработанных событий для удаления."""
    cleanup_processed_outbox_events.apply()
    assert EventOutbox.objects.count() == 0
