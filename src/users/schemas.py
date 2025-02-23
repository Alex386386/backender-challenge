from core.base_model import Model
from core.use_case import UseCaseRequest, UseCaseResponse
from users.models import User


class UserCreated(Model):
    email: str
    first_name: str
    last_name: str


class CreateUserRequest(UseCaseRequest):
    email: str
    first_name: str = ""
    last_name: str = ""


class CreateUserResponse(UseCaseResponse):
    result: User | None = None
    error: str = ""
