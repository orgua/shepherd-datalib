from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml
from pydantic import Field
from pydantic import constr
from pydantic import root_validator
from strenum import StrEnum

from .. import Fixtures
from .. import ShpModel
from ..model_shepherd import repr_str
from .mcu import MCU

fixture_path = Path(__file__).resolve().with_name("firmware_fixture.yaml")
fixtures = Fixtures(fixture_path, "testbed.firmware")


class FirmwareDType(StrEnum):
    hex = "hex"  # TODO: rename to base64_hex/elf and path_hex/elf
    elf = "elf"
    path = "path"


yaml.add_representer(FirmwareDType, repr_str)


class Firmware(ShpModel):
    uid: constr(
        strip_whitespace=True,
        to_lower=True,
        min_length=4,
        max_length=16,
    )
    name: str
    description: Optional[str]
    mcu: MCU
    data: str
    data_type: FirmwareDType

    # internal, TODO: together with uid these vars could be become a new template class
    owner: str
    group: str
    open2group: bool = False
    open2all: bool = False
    created: datetime = Field(default_factory=datetime.now)

    @root_validator(pre=True)
    def recursive_fill(cls, values: dict):
        values, chain = fixtures.inheritance(values)
        return values
