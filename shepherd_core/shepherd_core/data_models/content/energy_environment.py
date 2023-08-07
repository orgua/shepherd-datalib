from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import PositiveFloat
from pydantic import root_validator

from ...testbed_client import tb_client
from ..base.content import ContentModel


class EnergyDType(str, Enum):
    ivsample = "ivsample"
    ivsamples = "ivsample"
    ivcurve = "ivcurve"
    ivcurves = "ivcurve"
    isc_voc = "isc_voc"


class EnergyEnvironment(ContentModel):
    """Recording of meta-data representation of a testbed-component"""

    # General Metadata & Ownership -> ContentModel

    data_path: Path
    data_type: EnergyDType

    duration: PositiveFloat
    energy_Ws: PositiveFloat
    valid: bool = False

    # TODO: scale up/down voltage/current

    # additional descriptive metadata
    light_source: Optional[str] = None
    weather_conditions: Optional[str] = None
    indoor: Optional[bool] = None
    location: Optional[str] = None

    @root_validator(pre=True)
    def query_database(cls, values: dict) -> dict:
        values, _ = tb_client.try_completing_model(cls.__name__, values)
        return tb_client.fill_in_user_data(values)
