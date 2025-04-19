"""Hardware related inventory model."""

from typing import Optional

from pydantic import ConfigDict
from typing_extensions import Self

from ..data_models import ShpModel


class TargetInventory(ShpModel):
    """Hardware related inventory model."""

    cape: Optional[str] = None
    targets: list[str] = []  # noqa: RUF012

    model_config = ConfigDict(str_min_length=0)

    @classmethod
    def collect(cls) -> Self:
        model_dict = {}

        return cls(**model_dict)
