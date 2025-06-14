"""Collection of tasks for all observers included in experiment."""

from pathlib import Path
from typing import Annotated
from typing import Optional

from pydantic import Field
from pydantic import validate_call
from typing_extensions import Self
from typing_extensions import deprecated

from shepherd_core.data_models.base.content import IdInt
from shepherd_core.data_models.base.content import NameStr
from shepherd_core.data_models.base.shepherd import ShpModel
from shepherd_core.data_models.experiment.experiment import Experiment
from shepherd_core.data_models.testbed.testbed import Testbed

from .observer_tasks import ObserverTasks


class TestbedTasks(ShpModel):
    """Collection of tasks for all observers included in experiment."""

    name: NameStr
    observer_tasks: Annotated[list[ObserverTasks], Field(min_length=1, max_length=128)]

    # deprecated, TODO: remove before public release
    email_results: Annotated[Optional[bool], deprecated("not needed anymore")] = False
    owner_id: Annotated[Optional[IdInt], deprecated("not needed anymore")] = None

    @classmethod
    @validate_call
    def from_xp(cls, xp: Experiment, tb: Optional[Testbed] = None) -> Self:
        if tb is None:
            # TODO: is tb-argument really needed? prob. not
            tb = Testbed()  # this will query the first (and only) entry of client

        tgt_ids = xp.get_target_ids()
        obs_tasks = [ObserverTasks.from_xp(xp, tb, _id) for _id in tgt_ids]
        return cls(
            name=xp.name,
            observer_tasks=obs_tasks,
        )

    def get_observer_tasks(self, observer: str) -> Optional[ObserverTasks]:
        for tasks in self.observer_tasks:
            if observer == tasks.observer:
                return tasks
        return None

    def get_output_paths(self) -> dict[str, Path]:
        # TODO: computed field preferred, but they don't work here, as
        #  - they are always stored in yaml despite "repr=False"
        #  - solution will shift to some kind of "result"-datatype that is combinable
        values: dict[str, Path] = {}
        for obt in self.observer_tasks:
            values = {**values, **obt.get_output_paths()}
        return values
