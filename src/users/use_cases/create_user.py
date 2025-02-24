from typing import Any

import structlog
from django.db import transaction

from core import settings
from core.use_case import UseCase
from outbox.models import EventOutbox
from users.models import User
from users.schemas import CreateUserRequest, CreateUserResponse, UseCaseRequest

logger = structlog.get_logger(__name__)


class CreateUser(UseCase):
    def _get_context_vars(self, request: UseCaseRequest) -> dict[str, Any]:
        return {
            "email": request.email,
            "first_name": request.first_name,
            "last_name": request.last_name,
        }

    def _execute(self, request: CreateUserRequest) -> CreateUserResponse:
        logger.info("creating a new user")

        with transaction.atomic():
            user, created = User.objects.get_or_create(
                email=request.email,
                defaults={
                    "first_name": request.first_name,
                    "last_name": request.last_name,
                },
            )

            if created:
                logger.info("user has been created")
                self._log(user)
                return CreateUserResponse(result=user)

            logger.error("unable to create a new user")
            return CreateUserResponse(error="User with this email already exists")

    def _log(self, user: User) -> None:
        EventOutbox.objects.create(
            event_type="user_created",
            event_context={
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
            },
            environment=settings.ENVIRONMENT,
            metadata_version=1,
        )
        logger.info(
            "Event saved to Outbox", event_type="user_created", user_email=user.email,
        )
