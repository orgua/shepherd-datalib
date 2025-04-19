"""Configs for observer features like gpio- & power-tracing."""

from datetime import timedelta
from enum import Enum
from typing import Annotated
from typing import Optional

import numpy as np
from pydantic import Field
from pydantic import PositiveFloat
from pydantic import model_validator
from typing_extensions import Self

from ..base.shepherd import ShpModel
from ..testbed.gpio import GPIO


class PowerTracing(ShpModel, title="Config for Power-Tracing"):
    """Configuration for recording the Power-Consumption of the Target Nodes.

    TODO: postprocessing not implemented ATM
    """

    intermediate_voltage: bool = False
    # ⤷ for EMU: record buffer capacitor instead of output (good for V_out = const)
    #            this also includes current!

    # time
    delay: timedelta = 0  # seconds
    duration: Optional[timedelta] = None  # till EOF

    # post-processing
    calculate_power: bool = False
    samplerate: Annotated[int, Field(ge=10, le=100_000)] = 100_000  # down-sample
    discard_current: bool = False
    discard_voltage: bool = False
    # ⤷ reduce file-size by omitting current / voltage

    @model_validator(mode="after")
    def post_validation(self) -> Self:
        if self.delay and self.delay.total_seconds() < 0:
            raise ValueError("Delay can't be negative.")
        if self.duration and self.duration.total_seconds() < 0:
            raise ValueError("Duration can't be negative.")

        discard_all = self.discard_current and self.discard_voltage
        if not self.calculate_power and discard_all:
            raise ValueError("Error in config -> tracing enabled, but output gets discarded")
        if self.calculate_power:
            raise NotImplementedError("postprocessing not implemented ATM")
        return self


class GpioTracing(ShpModel, title="Config for GPIO-Tracing"):
    """Configuration for recording the GPIO-Output of the Target Nodes.

    TODO: postprocessing not implemented ATM
    """

    # initial recording
    mask: Annotated[int, Field(ge=0, lt=2**10)] = 0b11_1111_1111  # all
    # ⤷ TODO: custom mask not implemented in PRU, ATM
    gpios: Optional[Annotated[list[GPIO], Field(min_length=1, max_length=10)]] = None  # = all
    # ⤷ TODO: list of GPIO to build mask, one of both should be internal / computed field

    # time
    delay: timedelta = 0  # seconds
    duration: Optional[timedelta] = None  # till EOF

    # post-processing,
    uart_decode: bool = False
    # TODO: quickfix - uart-log currently done online in userspace
    # NOTE: gpio-tracing currently shows rather big - but rare - "blind" windows (~1-4us)
    uart_pin: GPIO = GPIO(name="GPIO8")
    uart_baudrate: Annotated[int, Field(ge=2_400, le=921_600)] = 115_200
    # TODO: add a "discard_gpio" (if only uart is wanted)

    @model_validator(mode="after")
    def post_validation(self) -> Self:
        if self.mask == 0:
            raise ValueError("Error in config -> tracing enabled but mask is 0")
        if self.delay and self.delay.total_seconds() < 0:
            raise ValueError("Delay can't be negative.")
        if self.duration and self.duration.total_seconds() < 0:
            raise ValueError("Duration can't be negative.")
        return self


class GpioLevel(str, Enum):
    """Options for setting the gpio-level or state."""

    low = "L"
    high = "H"
    toggle = "X"  # TODO: not the smartest decision for writing a converter


class GpioEvent(ShpModel, title="Config for a GPIO-Event"):
    """Configuration for a single GPIO-Event (Actuation)."""

    delay: PositiveFloat
    # ⤷ from start_time
    # ⤷ resolution 10 us (guaranteed, but finer steps are possible)
    gpio: GPIO
    level: GpioLevel
    period: Annotated[float, Field(ge=10e-6)] = 1
    # ⤷ time base of periodicity in s
    count: Annotated[int, Field(ge=1, le=4096)] = 1

    @model_validator(mode="after")
    def post_validation(self) -> Self:
        if not self.gpio.user_controllable():
            msg = f"GPIO '{self.gpio.name}' in actuation-event not controllable by user"
            raise ValueError(msg)
        return self

    def get_events(self) -> np.ndarray:
        stop = self.delay + self.count * self.period
        return np.arange(self.delay, stop, self.period)


class GpioActuation(ShpModel, title="Config for GPIO-Actuation"):
    """Configuration for a GPIO-Actuation-Sequence."""

    # TODO: not implemented ATM - decide if pru control sys-gpio or
    # TODO: not implemented ATM - reverses pru-gpio (preferred if possible)

    events: Annotated[list[GpioEvent], Field(min_length=1, max_length=1024)]

    def get_gpios(self) -> set:
        return {_ev.gpio for _ev in self.events}


class SystemLogging(ShpModel, title="Config for System-Logging"):
    """Configuration for recording Debug-Output of the Observers System-Services."""

    dmesg: bool = True
    ptp: bool = True
    shepherd: bool = True
    # TODO: rename to kernel, timesync, sheep
    # TODO: add utilization as option


# TODO: some more interaction would be good
#     - execute limited python-scripts
#     - send uart-frames
