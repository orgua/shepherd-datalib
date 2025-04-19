"""meta-data representation of a testbed-component (physical object)."""

from enum import Enum
from typing import Annotated
from typing import Optional

from pydantic import Field
from pydantic import model_validator

from ...testbed_client import tb_client
from ..base.content import IdInt
from ..base.content import NameStr
from ..base.content import SafeStr
from ..base.shepherd import ShpModel


class ProgrammerProtocol(str, Enum):
    """Options regarding the programming-protocol."""

    SWD = swd = "SWD"
    SBW = sbw = "SBW"
    JTAG = jtag = "JTAG"
    UART = uart = "UART"


class MCU(ShpModel, title="Microcontroller of the Target Node"):
    """meta-data representation of a testbed-component (physical object)."""

    id: IdInt
    name: NameStr
    description: SafeStr
    comment: Optional[SafeStr] = None

    platform: NameStr
    core: NameStr
    prog_protocol: ProgrammerProtocol
    prog_voltage: Annotated[float, Field(ge=1, le=5)] = 3
    prog_datarate: Annotated[int, Field(gt=0, le=1_000_000)] = 500_000

    fw_name_default: str
    # ⤷ can't be FW-Object (circular import)

    def __str__(self) -> str:
        return self.name

    @model_validator(mode="before")
    @classmethod
    def query_database(cls, values: dict) -> dict:
        values, _ = tb_client.try_completing_model(cls.__name__, values)
        return values
