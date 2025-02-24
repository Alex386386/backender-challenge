import pytest

from outbox.models import EventOutbox
from users.use_cases import (
    CreateUser,
    CreateUserRequest,
    CreateUserResponse,
)

pytestmark = [pytest.mark.django_db]


@pytest.fixture()
def f_use_case() -> CreateUser:
    return CreateUser()


def test_user_created(f_use_case: CreateUser) -> None:
    request = CreateUserRequest(
        email="test@email.com",
        first_name="Test",
        last_name="Testovich",
    )

    response: CreateUserResponse = f_use_case.execute(request)

    assert response.result.email == "test@email.com"
    assert response.error == ""

    event = EventOutbox.objects.filter(
        event_type="user_created", event_context__contains={"email": "test@email.com"},
    ).first()
    assert event is not None
    assert event.event_type == "user_created"
    assert event.event_context["email"] == "test@email.com"


def test_emails_are_unique(f_use_case: CreateUser) -> None:
    request = CreateUserRequest(
        email="test@email.com",
        first_name="Test",
        last_name="Testovich",
    )

    f_use_case.execute(request)
    response: CreateUserResponse = f_use_case.execute(request)

    assert response.result is None
    assert response.error == "User with this email already exists"

    events = EventOutbox.objects.filter(
        event_type="user_created", event_context__contains={"email": "test@email.com"},
    )
    assert events.count() == 1
