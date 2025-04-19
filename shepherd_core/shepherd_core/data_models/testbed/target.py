"""meta-data representation of a testbed-component (physical object)."""

from datetime import datetime
from typing import Annotated
from typing import Optional
from typing import Union

from pydantic import Field
from pydantic import model_validator

from ...testbed_client import tb_client
from ..base.content import IdInt
from ..base.content import NameStr
from ..base.content import SafeStr
from ..base.shepherd import ShpModel
from .mcu import MCU

IdInt16 = Annotated[int, Field(ge=0, lt=2**16)]

MCUPort = Annotated[int, Field(ge=1, le=2)]


class Target(ShpModel, title="Target Node (DuT)"):
    """meta-data representation of a testbed-component (physical object)."""

    id: IdInt
    name: NameStr
    version: NameStr
    description: SafeStr

    comment: Optional[SafeStr] = None

    active: bool = True
    created: datetime = Field(default_factory=datetime.now)

    testbed_id: Optional[IdInt16] = None
    # ⤷ is derived from ID (targets are still selected by id!)
    mcu1: Union[MCU, NameStr]
    mcu2: Union[MCU, NameStr, None] = None

    # TODO: programming pins per mcu should be here (or better in Cape)

    def __str__(self) -> str:
        return self.name

    @model_validator(mode="before")
    @classmethod
    def query_database(cls, values: dict) -> dict:
        values, _ = tb_client.try_completing_model(cls.__name__, values)

        # post correction
        for _mcu in ["mcu1", "mcu2"]:
            if isinstance(values.get(_mcu), str):
                values[_mcu] = MCU(name=values[_mcu])
                # ⤷ this will raise if default is faulty
            elif isinstance(values.get(_mcu), dict):
                values[_mcu] = MCU(**values[_mcu])
        if values.get("testbed_id") is None:
            values["testbed_id"] = values.get("id") % 2**16

        return values
