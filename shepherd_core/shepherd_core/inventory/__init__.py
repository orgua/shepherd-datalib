"""Creates an overview for shepherd-host-machines.

This will collect:
- relevant software-versions
- system-parameters
- hardware-config.
"""

from datetime import datetime
from datetime import timedelta
from pathlib import Path
from typing import Annotated

from pydantic import Field
from typing_extensions import Self

from ..data_models import ShpModel
from .python import PythonInventory
from .system import SystemInventory
from .target import TargetInventory

__all__ = [
    "Inventory",
    "InventoryList",
    "PythonInventory",
    "SystemInventory",
    "TargetInventory",
]


class Inventory(PythonInventory, SystemInventory, TargetInventory):
    """Complete inventory for one device.

    Has all child-parameters.
    """

    hostname: str
    created: datetime

    @classmethod
    def collect(cls) -> Self:
        # one by one for more precise error messages
        # NOTE: system is first, as it must take a precise timestamp
        sid = SystemInventory.collect().model_dump(exclude_unset=True, exclude_defaults=True)
        pid = PythonInventory.collect().model_dump(exclude_unset=True, exclude_defaults=True)
        tid = TargetInventory.collect().model_dump(exclude_unset=True, exclude_defaults=True)
        model = {**pid, **sid, **tid}
        # make important metadata available at root level
        model["created"] = sid["timestamp"]
        model["hostname"] = sid["hostname"]
        return cls(**model)


class InventoryList(ShpModel):
    """Collection of inventories for several devices."""

    elements: Annotated[list[Inventory], Field(min_length=1)]

    def to_csv(self, path: Path) -> None:
        """Generate a CSV.

        TODO: pretty messed up (raw lists and dicts for sub-elements)
        numpy.savetxt -> too basic
        np.concatenate(content).reshape((len(content), len(content[0]))).
        """
        if path.is_dir():
            path = path / "inventory.yaml"
        with path.resolve().open("w") as fd:
            fd.write(", ".join(self.elements[0].model_dump().keys()) + "\r\n")
            for item in self.elements:
                content = list(item.model_dump().values())
                content = ["" if value is None else str(value) for value in content]
                fd.write(", ".join(content) + "\r\n")

    def warn(self) -> dict:
        warnings = {}
        ts_earl = min([_e.created.timestamp() for _e in self.elements])
        for _e in self.elements:
            if _e.uptime > timedelta(hours=30).total_seconds():
                warnings["uptime"] = f"[{self.hostname}] restart is recommended"
            if (_e.created.timestamp() - ts_earl) > 10:
                warnings["time_delta"] = f"[{self.hostname}] time-sync has failed"

        # turn  dict[hostname][type] = val
        # to    dict[type][val] = list[hostnames]
        _inp = {
            _e.hostname: _e.model_dump(exclude_unset=True, exclude_defaults=True)
            for _e in self.elements
        }
        result = {}
        for _host, _types in _inp.items():
            for _type, _val in _types.items():
                if _type not in result:
                    result[_type] = {}
                if _val not in result[_type]:
                    result[_type][_val] = []
                result[_type][_val].append(_host)
        rescnt = {_key: len(_val) for _key, _val in result.items()}
        t_unique = [
            "h5py",
            "numpy",
            "pydantic",
            "python",
            "shepherd_core",
            "shepherd_sheep",
            "yaml",
            "zstandard",
        ]
        for _key in t_unique:
            if rescnt[_key] > 1:
                warnings[_key] = f"[{_key}] VersionMismatch - {result[_key]}"

        # TODO: finish with more potential warnings
        return warnings
