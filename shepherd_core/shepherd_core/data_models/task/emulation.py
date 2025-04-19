"""Configuration for the Observer in Emulation-Mode."""

import copy
from datetime import datetime
from datetime import timedelta
from enum import Enum
from pathlib import Path
from typing import Annotated
from typing import Optional
from typing import Union

from pydantic import Field
from pydantic import model_validator
from pydantic import validate_call
from typing_extensions import Self

from ..base.content import IdInt
from ..base.shepherd import ShpModel
from ..base.timezone import local_tz
from ..content.virtual_source import VirtualSourceConfig
from ..experiment.experiment import Experiment
from ..experiment.observer_features import GpioActuation
from ..experiment.observer_features import GpioTracing
from ..experiment.observer_features import PowerTracing
from ..experiment.observer_features import SystemLogging
from ..testbed import Testbed
from ..testbed.cape import TargetPort


class Compression(str, Enum):
    """Options for choosing a dataset-compression."""

    lzf = default = "lzf"  # not native hdf5
    gzip1 = gzip = 1  # higher compr & load
    null = None
    # NOTE: lzf & external file-compression (xz or zstd) work better than gzip
    #       -> even with additional compression


compressions_allowed: list = [None, "lzf", 1]
c_translate = {"lzf": "lzf", "1": 1, "None": None, None: None}


class EmulationTask(ShpModel):
    """Configuration for the Observer in Emulation-Mode."""

    # General config
    input_path: Path
    # ⤷ hdf5 file containing harvesting data
    output_path: Optional[Path] = None
    # ⤷ dir- or file-path for storing the recorded data:
    #   - providing a directory -> file is named emu_timestamp.h5
    #   - for a complete path the filename is not changed except it exists and
    #     overwrite is disabled -> emu#num.h5
    # TODO: should the output-path be mandatory?
    force_overwrite: bool = False
    # ⤷ Overwrite existing file
    output_compression: Optional[Compression] = Compression.default
    # ⤷ should be lzf, 1 (gzip level 1) or None (order of recommendation)
    time_start: Optional[datetime] = None
    # timestamp or unix epoch time, None = ASAP
    duration: Optional[timedelta] = None
    # ⤷ Duration of recording in seconds, None = till EOF
    abort_on_error: bool = False  # TODO: remove, should not exist

    # emulation-specific
    use_cal_default: bool = False
    # ⤷ Use default calibration values, skip loading from EEPROM

    enable_io: bool = False
    # TODO: add direction of pins! also it seems error-prone when only setting _tracing
    # ⤷ Switch the GPIO level converter to targets on/off
    #   pre-req for sampling gpio,
    io_port: TargetPort = TargetPort.A
    # ⤷ Either Port A or B that gets connected to IO
    pwr_port: TargetPort = TargetPort.A
    # ⤷ chosen port will be current-monitored (main, connected to virtual Source),
    #   the other port is aux
    voltage_aux: Union[Annotated[float, Field(ge=0, le=4.5)], str] = 0
    # ⤷ aux_voltage options:
    #   - 0-4.5 for specific const Voltage (0 V = disabled),
    #   - "buffer" will output intermediate voltage (storage cap of vsource),
    #   - "main" will mirror main target voltage

    # sub-elements, could be partly moved to emulation
    virtual_source: VirtualSourceConfig = VirtualSourceConfig(name="neutral")
    # ⤷ Use the desired setting for the virtual source,
    #   provide parameters or name like BQ25570

    power_tracing: Optional[PowerTracing] = PowerTracing()
    gpio_tracing: Optional[GpioTracing] = GpioTracing()
    gpio_actuation: Optional[GpioActuation] = None
    sys_logging: Optional[SystemLogging] = SystemLogging()

    verbose: Annotated[int, Field(ge=0, le=4)] = 2
    # ⤷ 0=Errors, 1=Warnings, 2=Info, 3=Debug, TODO: just bool now, systemwide

    @model_validator(mode="before")
    @classmethod
    def pre_correction(cls, values: dict) -> dict:
        # convert & add local timezone-data
        has_time = values.get("time_start") is not None
        if has_time and isinstance(values["time_start"], (int, float)):
            values["time_start"] = datetime.fromtimestamp(values["time_start"], tz=local_tz())
        if has_time and isinstance(values["time_start"], str):
            values["time_start"] = datetime.fromisoformat(values["time_start"])
        if has_time and values["time_start"].tzinfo is None:
            values["time_start"] = values["time_start"].astimezone()
        return values

    @model_validator(mode="after")
    def post_validation(self) -> Self:
        # TODO: limit paths
        has_time = self.time_start is not None
        time_now = datetime.now().astimezone()
        if has_time and self.time_start < time_now:
            msg = (
                "Start-Time for Emulation can't be in the past "
                f"('{self.time_start}' vs '{time_now}'."
            )
            raise ValueError(msg)
        if self.duration and self.duration.total_seconds() < 0:
            raise ValueError("Task-Duration can't be negative.")
        if isinstance(self.voltage_aux, str) and self.voltage_aux not in {
            "main",
            "buffer",
        }:
            raise ValueError("Voltage Aux must be in float (0 - 4.5) or string 'main' / 'mid'.")
        if self.gpio_actuation is not None:
            raise ValueError("GPIO Actuation not yet implemented!")
        return self

    @classmethod
    @validate_call
    def from_xp(cls, xp: Experiment, tb: Testbed, tgt_id: IdInt, root_path: Path) -> Self:
        obs = tb.get_observer(tgt_id)
        tgt_cfg = xp.get_target_config(tgt_id)

        return cls(
            input_path=tgt_cfg.energy_env.data_path,
            output_path=root_path / f"emu_{obs.name}.h5",
            time_start=copy.copy(xp.time_start),
            duration=xp.duration,
            abort_on_error=xp.abort_on_error,
            enable_io=(tgt_cfg.gpio_tracing is not None) or (tgt_cfg.gpio_actuation is not None),
            io_port=obs.get_target_port(tgt_id),
            pwr_port=obs.get_target_port(tgt_id),
            virtual_source=tgt_cfg.virtual_source,
            power_tracing=tgt_cfg.power_tracing,
            gpio_tracing=tgt_cfg.gpio_tracing,
            gpio_actuation=tgt_cfg.gpio_actuation,
            sys_logging=xp.sys_logging,
        )


# TODO: herdConfig
#  - store if path is remote (read & write)
#   -> so files need to be fetched or have a local path
