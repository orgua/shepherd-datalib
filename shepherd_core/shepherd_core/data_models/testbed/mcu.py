from enum import Enum
from typing import Optional

from pydantic import confloat
from pydantic import conint
from pydantic import root_validator

from ...testbed_client import tb_client
from ..base.content import IdInt
from ..base.content import NameStr
from ..base.content import SafeStr
from ..base.shepherd import ShpModel


class ProgrammerProtocol(str, Enum):
    SWD = "SWD"
    swd = "SWD"
    SBW = "SBW"
    sbw = "SBW"
    JTAG = "JTAG"
    jtag = "JTAG"
    UART = "UART"
    uart = "UART"


class MCU(ShpModel, title="Microcontroller of the Target Node"):
    """meta-data representation of a testbed-component (physical object)"""

    id: IdInt  # noqa: A003
    name: NameStr
    description: SafeStr
    comment: Optional[SafeStr] = None

    platform: NameStr
    core: NameStr
    prog_protocol: ProgrammerProtocol
    prog_voltage: confloat(ge=1, le=5) = 3
    prog_datarate: conint(gt=0, le=1_000_000) = 500_000

    fw_name_default: str
    # ⤷ can't be FW-Object (circular import)

    def __str__(self):
        return self.name

    @root_validator(pre=True)
    def query_database(cls, values: dict) -> dict:
        model_name = type(cls).__name__
        values = tb_client.query(model_name, values.get("id"), values.get("name"))
        values, _ = tb_client.inheritance(model_name, values)
        return values
