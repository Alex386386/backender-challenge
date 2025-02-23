from core.base_model import Model


class UseCaseRequest(Model):
    pass


class UseCaseResponse(Model):
    result: any = None
    error: str = ""
