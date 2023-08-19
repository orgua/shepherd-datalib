from datetime import datetime
from typing import Optional
from typing import Union

from pydantic import Field
from pydantic import model_validator
from typing_extensions import Annotated

from ...testbed_client import tb_client
from ..base.content import IdInt
from ..base.content import NameStr
from ..base.content import SafeStr
from ..base.shepherd import ShpModel
from .mcu import MCU

IdInt16 = Annotated[int, Field(ge=0, lt=2**16)]

MCUPort = Annotated[int, Field(ge=1, le=2)]


class Target(ShpModel, title="Target Node (DuT)"):
    """meta-data representation of a testbed-component (physical object)"""

    id: IdInt  # noqa: A003
    name: NameStr
    version: NameStr
    description: SafeStr

    comment: Optional[SafeStr] = None

    created: datetime = Field(default_factory=datetime.now)

    fw_id: Optional[IdInt16] = None
    mcu1: Union[MCU, NameStr]
    mcu2: Union[MCU, NameStr, None] = None
    #

    # TODO programming pins per mcu should be here (or better in Cape)

    def __str__(self):
        return self.name

    @model_validator(mode="before")
    @classmethod
    def query_database(cls, values: dict) -> dict:
        values, _ = tb_client.try_completing_model(cls.__name__, values)

        # post correction
        if isinstance(values.get("mcu1"), str):
            values["mcu1"] = MCU(name=values["mcu1"])
            # ⤷ this will raise if default is faulty
        if isinstance(values.get("mcu2"), str):
            values["mcu2"] = MCU(name=values["mcu2"])
        if values.get("fw_id") is None:
            values["fw_id"] = values.get("id") % 2**16

        return values
