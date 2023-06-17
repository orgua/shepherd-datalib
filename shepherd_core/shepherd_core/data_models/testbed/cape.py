from datetime import date
from datetime import datetime
from enum import Enum
from typing import Optional
from typing import Union

from pydantic import Field
from pydantic import root_validator

from ...testbed_client import tb_client
from ..base.content import IdInt
from ..base.content import NameStr
from ..base.content import SafeStr
from ..base.shepherd import ShpModel


class TargetPort(str, Enum):
    A = "A"
    B = "B"
    a = "A"
    b = "B"


class Cape(ShpModel, title="Shepherd-Cape"):
    """meta-data representation of a testbed-component (physical object)"""

    id: IdInt  # noqa: A003
    name: NameStr
    version: NameStr
    description: SafeStr
    comment: Optional[SafeStr] = None
    # TODO: wake_interval, calibration

    created: Union[date, datetime] = Field(default_factory=datetime.now)
    calibrated: Union[date, datetime, None] = None

    def __str__(self):
        return self.name

    @root_validator(pre=True)
    def query_database(cls, values: dict) -> dict:
        values = tb_client.query(cls.__name__, values.get("id"), values.get("name"))
        values, _ = tb_client.inheritance(cls.__name__, values)
        return values
