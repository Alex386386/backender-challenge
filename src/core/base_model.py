import datetime as dt
from functools import cached_property

from pydantic import BaseModel


class Model(BaseModel):
    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            dt.date: lambda v: v.isoformat(),
            dt.datetime: lambda v: v.isoformat(),
            Exception: lambda e: str(e),
        }
        ignored_types = (cached_property,)
