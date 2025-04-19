"""meta-data representation of a testbed-component (physical object)."""

from enum import Enum
from typing import Annotated
from typing import Optional

from pydantic import Field
from pydantic import StringConstraints
from pydantic import model_validator
from typing_extensions import Self

from ...testbed_client import tb_client
from ..base.content import IdInt
from ..base.content import NameStr
from ..base.content import SafeStr
from ..base.shepherd import ShpModel


class Direction(str, Enum):
    """Options for pin-direction."""

    Input = IN = "IN"
    Output = OUT = "OUT"
    Bidirectional = IO = "IO"


class GPIO(ShpModel, title="GPIO of Observer Node"):
    """meta-data representation of a testbed-component."""

    id: IdInt
    name: NameStr
    description: Optional[SafeStr] = None
    comment: Optional[SafeStr] = None

    direction: Direction = Direction.Input
    dir_switch: Optional[Annotated[str, StringConstraints(max_length=32)]] = None

    reg_pru: Optional[Annotated[str, StringConstraints(max_length=10)]] = None
    pin_pru: Optional[Annotated[str, StringConstraints(max_length=10)]] = None
    reg_sys: Optional[Annotated[int, Field(ge=0)]] = None
    pin_sys: Optional[Annotated[str, StringConstraints(max_length=10)]] = None

    def __str__(self) -> str:
        return self.name

    @model_validator(mode="before")
    @classmethod
    def query_database(cls, values: dict) -> dict:
        values, _ = tb_client.try_completing_model(cls.__name__, values)
        return values

    @model_validator(mode="after")
    def post_validation(self) -> Self:
        # ensure that either pru or sys is used, otherwise instance is considered faulty
        no_pru = (self.reg_pru is None) or (self.pin_pru is None)
        no_sys = (self.reg_sys is None) or (self.pin_sys is None)
        if no_pru and no_sys:
            msg = (
                "GPIO-Instance is faulty -> "
                f"it needs to use pru or sys, content: {self.model_dump()}"
            )
            raise ValueError(msg)
        return self

    def user_controllable(self) -> bool:
        return ("gpio" in self.name.lower()) and (self.direction in {"IO", "OUT"})
