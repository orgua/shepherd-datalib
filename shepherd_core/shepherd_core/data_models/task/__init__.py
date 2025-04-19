"""Module for task-related data-modules.

These models import externally from all other model-modules!
"""

from pathlib import Path
from typing import Optional
from typing import Union

import yaml

from ...logger import logger
from ..base.shepherd import ShpModel
from ..base.wrapper import Wrapper
from .emulation import Compression
from .emulation import EmulationTask
from .firmware_mod import FirmwareModTask
from .harvest import HarvestTask
from .observer_tasks import ObserverTasks
from .programming import ProgrammingTask
from .testbed_tasks import TestbedTasks

__all__ = [
    "Compression",
    "EmulationTask",
    "FirmwareModTask",
    "HarvestTask",
    "ObserverTasks",
    "ProgrammingTask",
    "TestbedTasks",
    "extract_tasks",
    "prepare_task",
]


def prepare_task(config: Union[ShpModel, Path, str], observer: Optional[str] = None) -> Wrapper:
    """Open file and extract tasks.

    - Open file (from Path or str of Path)
    - wraps task-model
    - and if it's an TestbedTasks it will extract the correct ObserverTask
    """
    if isinstance(config, str):
        config = Path(config)

    if isinstance(config, Path):
        with config.resolve().open() as shp_file:
            shp_dict = yaml.safe_load(shp_file)
        shp_wrap = Wrapper(**shp_dict)
    elif isinstance(config, ShpModel):
        shp_wrap = Wrapper(
            datatype=type(config).__name__,
            parameters=config.model_dump(),
        )
    else:
        raise TypeError("had unknown input: %s", type(config))

    if shp_wrap.datatype == TestbedTasks.__name__:
        if observer is None:
            logger.debug(
                "Task-Set contained TestbedTasks & no observer was provided -> will return TB-Tasks"
            )
            return shp_wrap
        tbt = TestbedTasks(**shp_wrap.parameters)
        logger.debug("Loading Testbed-Tasks %s for %s", tbt.name, observer)
        obt = tbt.get_observer_tasks(observer)
        if obt is None:
            raise ValueError("Observer '%s' is not in TestbedTask-Set", observer)
        shp_wrap = Wrapper(
            datatype=type(obt).__name__,
            parameters=obt.model_dump(),
        )
    return shp_wrap


def extract_tasks(shp_wrap: Wrapper, *, no_task_sets: bool = True) -> list[ShpModel]:
    """Make the individual task-sets usable for each observer."""
    if shp_wrap.datatype == ObserverTasks.__name__:
        obt = ObserverTasks(**shp_wrap.parameters)
        content = obt.get_tasks()
    elif shp_wrap.datatype == EmulationTask.__name__:
        content = [EmulationTask(**shp_wrap.parameters)]
    elif shp_wrap.datatype == HarvestTask.__name__:
        content = [HarvestTask(**shp_wrap.parameters)]
    elif shp_wrap.datatype == FirmwareModTask.__name__:
        content = [FirmwareModTask(**shp_wrap.parameters)]
    elif shp_wrap.datatype == ProgrammingTask.__name__:
        content = [ProgrammingTask(**shp_wrap.parameters)]
    elif shp_wrap.datatype == TestbedTasks.__name__:
        if no_task_sets:
            raise ValueError("Model in Wrapper was TestbedTasks -> Task-Sets not allowed!")
        content = [TestbedTasks(**shp_wrap.parameters)]
    else:
        raise ValueError("Extractor had unknown task: %s", shp_wrap.datatype)

    return content
