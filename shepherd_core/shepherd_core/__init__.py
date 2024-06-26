"""Bundled core features used by several systems.

Provides classes for storing and retrieving sampled IV data to/from
HDF5 files.

"""

from .data_models.base.calibration import Calc_t
from .data_models.base.calibration import CalibrationCape
from .data_models.base.calibration import CalibrationEmulator
from .data_models.base.calibration import CalibrationHarvester
from .data_models.base.calibration import CalibrationPair
from .data_models.base.calibration import CalibrationSeries
from .data_models.base.timezone import local_now
from .data_models.base.timezone import local_tz
from .data_models.task.emulation import Compression
from .inventory import Inventory
from .logger import get_verbose_level
from .logger import increase_verbose_level
from .logger import logger
from .reader import Reader
from .testbed_client.client import TestbedClient
from .testbed_client.client import tb_client
from .writer import Writer

__version__ = "2024.5.1"

__all__ = [
    "Reader",
    "Writer",
    "get_verbose_level",
    "increase_verbose_level",
    "logger",
    "CalibrationCape",
    "CalibrationSeries",
    "CalibrationEmulator",
    "CalibrationHarvester",
    "CalibrationPair",
    "local_tz",
    "local_now",
    "Calc_t",
    "Compression",
    "TestbedClient",
    "tb_client",  # using this (instead of the Class) is the cleaner, but less pythonic way
    "Inventory",
]
