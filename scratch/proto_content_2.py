import yaml
import shutil

from enum import Enum
from pathlib import Path
from typing import Any
from typing import Optional
from typing import List, Annotated
from typing_extensions import Self

from collections.abc import Iterable
from copy import deepcopy

from pydantic import PositiveFloat, model_validator, BaseModel, Field

from shepherd_core import logger
from shepherd_core.data_models import ShpModel

class EnergyDType(str, Enum):
    """Data-Type-Options for energy environments."""

    ivtrace = ivsample = ivsamples = "ivsample"
    ivsurface = ivcurve = ivcurves = "ivcurve"
    isc_voc = "isc_voc"

# TODO export of eenv

class EnergyProfile(BaseModel):
    data_path: Path
    #⤷  (absolute) path to the raw data

    max_harvestable_energy: PositiveFloat
    #⤷  in Ws; for I-V traces: total energy; for I-V surfaces: maximum energy (always at the ideal operating point); human readable string

    data_type: EnergyDType
    #⤷  data type of all profiles in this environment

    metadata: Optional[dict] = None
    #⤷  metadata relating to this profile specifically (e.g. node location in an experiment, transducer for this node, etc.)

    @model_validator(mode="before")
    @classmethod
    def cast_path(cls, values: dict[str, Any]) -> dict[str, Any]:
        if "data_path" in values and isinstance(values["data_path"], Iterable):
            values["data_path"] = values["data_path"].absolute()
        return values


class EnergyEnvironment2(ShpModel):
    profiles: List[EnergyProfile]
    #⤷  list of individual profiles that make up the environment

    duration: PositiveFloat
    #⤷  in s; duration of the recorded environment (of all profiles)

    # TODO: datalib_version ??
    metadata: Optional[str] = None
    #⤷  information about the environment (e.g. recording tool/generation script, address/GPS, building/outside, weather, etc.); human readable string

    def __len__(self):
        return len(self.profiles)

    def __add__(self, other):
        return self.model_copy(deep=True, update={
            "profiles": deepcopy(self.profiles + other.profiles)
        })

    def __getitem__(self, value):
        return self.model_copy(deep=True, update={
            "profiles": deepcopy(self.profiles[value])
        })

    def export(self, output_path: Path):
        output_path.mkdir(exist_ok=False)

        # Copy data files

        for (i, profile) in enumerate(self.profiles):
            # Number the sheep to avoid collisions. Preserve extensions
            relative_path = [f'sheep{i}{profile.data_path.suffix}' for profile in self.profiles]
            shutil.copy(profile.data_path, output_path / relative_path)

        # Create information file

        content = self.model_dump()
        # Use relative paths now
        for (i, path) in relative_paths:
            content['profiles'][i]['data_path'] = path

        with open('eenv.yaml', 'w') as file:
            yaml.dump(content, file, default_flow_style=False)
        

class TargetConfig2(ShpModel):
    """Prototype."""

    target_IDs: Annotated[list[int], Field(min_length=1, max_length=128)]
    eenv: EnergyEnvironment2

    @model_validator(mode="after")
    def check_eenv_count(self) -> Self:
        eenvs = len(self.eenv)
        targets = len(self.target_IDs)
        if eenvs == targets:
            return self

        if eenvs > targets:
            msg = f'Creating config for {targets} sheep with an energy environment that contains {eenvs} sheep. Remainder of the environment will be discarded.'
            logger.warning(msg)
            return self

        if eenvs == 1:
            msg = f'Creating config for {targets} sheep with an energy environment that contains {eenvs} sheep. Environment will be duplicated across the targets.'
            logger.warning(msg)
            return self

        raise ValueError(f'Trying to create config for {targets} sheep with an energy environment that contains {eenvs} sheep. Can not infer a mapping of environment -> targets. Please use a larger environment.')

# TODO remove tests
if __name__ == "__main__":
    from pprint import pprint

    path1 = Path('./shp1.h5')
    path2 = Path('./shp3.h5')
    path1.touch()
    path2.touch()
    profile1 = EnergyProfile(data_path=path1, data_type=EnergyDType.ivtrace, max_harvestable_energy=1)
    profile2 = EnergyProfile(data_path=path2, data_type=EnergyDType.ivtrace, max_harvestable_energy=1)
    test = EnergyEnvironment2(profiles=[profile1, profile2], duration=1)
    pprint(test)

    test2 = test[1:] + test[:1]
    pprint(test2)

    test2.export(Path('./export'))

    TargetConfig2(target_IDs=range(2), eenv=test)
    TargetConfig2(target_IDs=range(1), eenv=test)
    TargetConfig2(target_IDs=range(3), eenv=test[:1])
    TargetConfig2(target_IDs=range(4), eenv=test)
