import json

from clickhouse_connect.driver.query import QueryResult


def check_in_result(event_id: int, log: QueryResult) -> bool:
    found_event: bool = False
    for row in log.result_rows:
        event_data = json.loads(row[3])
        if event_data.get("event_id") == event_id:
            found_event = True
            break
    return found_event
