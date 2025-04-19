"""Models for the calibration-data to convert between raw & SI-Values."""

import struct
from collections.abc import Generator
from collections.abc import Mapping
from collections.abc import Sequence
from typing import Callable
from typing import Optional
from typing import TypeVar
from typing import Union

import numpy as np
from numpy.typing import NDArray
from pydantic import Field
from pydantic import PositiveFloat
from pydantic import conbytes
from pydantic import constr
from pydantic import validate_call
from typing_extensions import Self

from ...calibration_hw_def import adc_current_to_raw
from ...calibration_hw_def import adc_voltage_to_raw
from ...calibration_hw_def import dac_voltage_to_raw
from .shepherd import ShpModel
from .timezone import local_iso_date

Calc_t = TypeVar("Calc_t", NDArray[np.float64], float)


def dict_generator(
    in_dict: Union[Mapping, Sequence], pre: Optional[list] = None
) -> Generator[list, None, None]:
    """Recursive helper-function to generate a 1D-List(or not?).

    TODO: isn't that a 1D-List generator?
    """
    pre = pre[:] if pre else []
    if isinstance(in_dict, Mapping):
        for key, value in in_dict.items():
            if isinstance(value, Mapping):
                yield from dict_generator(value, [*pre, key])
            elif isinstance(value, Sequence):
                for v in value:
                    yield from dict_generator(v, [*pre, key])
            else:
                yield [*pre, key, value]
    else:
        yield [*pre, in_dict]


class CalibrationPair(ShpModel):
    """SI-value [SI-Unit] = raw-value * gain + offset."""

    gain: PositiveFloat
    offset: float = 0
    unit: Optional[str] = None  # TODO: add units when used

    def raw_to_si(self, values_raw: Calc_t, *, allow_negative: bool = True) -> Calc_t:
        """Convert between physical units and raw unsigned integers."""
        values_si = values_raw * self.gain + self.offset
        if not allow_negative:
            if isinstance(values_si, np.ndarray):
                values_si[values_si < 0.0] = 0.0
                # if pyright still complains, cast with .astype(float)
            else:
                values_si = float(max(values_si, 0.0))
        elif not isinstance(values_si, np.ndarray):
            values_si = float(values_si)
        return values_si

    def si_to_raw(self, values_si: Calc_t) -> Calc_t:
        """Convert between physical units and raw unsigned integers."""
        values_raw = (values_si - self.offset) / self.gain
        if isinstance(values_raw, np.ndarray):
            values_raw[values_raw < 0.0] = 0.0
            values_raw = np.around(values_raw)
            # TODO: overflow should also be prevented (add bit-width) -> fail or warn at both?
        else:
            values_raw = round(max(values_raw, 0.0))
        return values_raw

    @classmethod
    def from_fn(cls, fn: Callable, unit: Optional[str] = None) -> Self:
        """Probe linear function to determine scaling values."""
        offset = fn(0, limited=False)
        gain_inv = fn(1.0, limited=False) - offset
        return cls(gain=1.0 / float(gain_inv), offset=-float(offset) / gain_inv, unit=unit)


cal_hrv_legacy = {  # legacy translator
    "dac_voltage_a": "dac_V_Sim",
    "dac_voltage_b": "dac_V_Hrv",
    "adc_current": "adc_C_Hrv",  # datalog current
    "adc_voltage": "adc_V_Sense",  # datalog voltage
}


class CalibrationHarvester(ShpModel):
    """Container for all calibration-pairs for that device."""

    dac_V_Hrv: CalibrationPair = CalibrationPair.from_fn(dac_voltage_to_raw, unit="V")
    dac_V_Sim: CalibrationPair = CalibrationPair.from_fn(dac_voltage_to_raw, unit="V")
    adc_V_Sense: CalibrationPair = CalibrationPair.from_fn(adc_voltage_to_raw, unit="V")
    adc_C_Hrv: CalibrationPair = CalibrationPair.from_fn(adc_current_to_raw, unit="A")

    def export_for_sysfs(self) -> dict:
        """Convert and write the essential data.

        [scaling according to commons.h]
        # ADC-C is handled in nA (nano-ampere), gain is shifted by 8 bit
        # ADC-V is handled in uV (micro-volt), gain is shifted by 8 bit
        # DAC-V is handled in uV (micro-volt), gain is shifted by 20 bit
        """
        cal_set = {
            "adc_current_gain": round(1e9 * (2**8) * self.adc_C_Hrv.gain),
            "adc_current_offset": round(1e9 * (2**0) * self.adc_C_Hrv.offset),
            "adc_voltage_gain": round(1e6 * (2**8) * self.adc_V_Sense.gain),
            "adc_voltage_offset": round(1e6 * (2**0) * self.adc_V_Sense.offset),
            "dac_voltage_gain": round((2**20) / (1e6 * self.dac_V_Hrv.gain)),
            "dac_voltage_offset": round(1e6 * (2**0) * self.dac_V_Hrv.offset),
        }
        for key, value in cal_set.items():
            if (("gain" in key) and not (0 <= value < 2**32)) or (
                ("offset" in key) and not (-(2**31) <= value < 2**31)
            ):
                msg = f"Value ({key}={value}) exceeds uint32-container"
                raise ValueError(msg)
        return cal_set


cal_emu_legacy = {  # legacy translator
    "dac_voltage_a": "dac_V_A",
    "dac_voltage_b": "dac_V_B",  # datalog voltage
    "adc_current": "adc_C_A",  # datalog current
    "adc_voltage": "adc_C_B",
}


class CalibrationEmulator(ShpModel):
    """Container for all calibration-pairs for that device.

    Differentiates between both target-ports A/B.
    """

    dac_V_A: CalibrationPair = CalibrationPair.from_fn(dac_voltage_to_raw, unit="V")
    dac_V_B: CalibrationPair = CalibrationPair.from_fn(dac_voltage_to_raw, unit="V")
    adc_C_A: CalibrationPair = CalibrationPair.from_fn(adc_current_to_raw, unit="A")
    adc_C_B: CalibrationPair = CalibrationPair.from_fn(adc_current_to_raw, unit="A")

    def export_for_sysfs(self) -> dict:
        """Convert and write the essential data.

        [scaling according to commons.h]
        # ADC-C is handled in nA (nano-ampere), gain is shifted by 8 bit
        # ADC-V -> unused by vsrc / emu
        # DAC-V is handled in uV (micro-volt), gain is shifted by 20 bit
        TODO: current impl does not distinguish target_ports for DAC
        """
        cal_set = {
            "adc_current_gain": round(1e9 * (2**8) * self.adc_C_A.gain),
            "adc_current_offset": round(1e9 * (2**0) * self.adc_C_A.offset),
            "adc_voltage_gain": round(1e6 * (2**8) * 1),
            "adc_voltage_offset": round(1e6 * (2**0) * 0),
            "dac_voltage_gain": round((2**20) / (1e6 * self.dac_V_A.gain)),
            "dac_voltage_offset": round(1e6 * (2**0) * self.dac_V_A.offset),
        }
        for key, value in cal_set.items():
            if (("gain" in key) and not (0 <= value < 2**32)) or (
                ("offset" in key) and not (-(2**31) <= value < 2**31)
            ):
                msg = f"Value ({key}={value}) exceeds uint32-container"
                raise ValueError(msg)
        return cal_set


class CapeData(ShpModel):
    """Representation of Beaglebone Cape information.

    User must at least provide serial-number on creation.

    According to BeagleBone specifications, each cape should host an EEPROM
    that contains some standardized information about the type of cape,
    manufacturer, version etc.

    `See<https://github.com/beagleboard/beaglebone-black/wiki/System-Reference-Manual#824_EEPROM_Data_Format>`_
    """

    header: conbytes(max_length=4) = b"\xaa\x55\x33\xee"
    eeprom_revision: constr(max_length=2) = "A2"
    board_name: constr(max_length=32) = "BeagleBone SHEPHERD2 Cape"
    version: constr(max_length=4) = "24B0"
    manufacturer: constr(max_length=16) = "NES TU DRESDEN"
    part_number: constr(max_length=16) = "BB-SHPRD"

    serial_number: constr(max_length=12)

    cal_date: constr(max_length=12) = Field(default_factory=local_iso_date)
    # ⤷ produces something like '2023-01-01'

    def __repr__(self) -> str:  # TODO: override useful?
        """string-representation allows print(model)."""
        return str(self.model_dump())


class CalibrationCape(ShpModel):
    """Represents calibration data of shepherd cape.

    Defines the format of calibration data and provides convenient functions
    to read and write calibration data.

    YAML: .to_file() and .from_file() already in ShpModel
    """

    cape: Optional[CapeData] = None
    host: Optional[str] = None

    harvester: CalibrationHarvester = CalibrationHarvester()
    emulator: CalibrationEmulator = CalibrationEmulator()

    @classmethod
    def from_bytestr(cls, data: bytes, cape: Optional[CapeData] = None) -> Self:
        """Instantiate calibration data based on byte string.

        This is mainly used to deserialize data read from an EEPROM memory.

        Args:
        ----
            data: Byte string containing calibration data.
            cape: data can be supplied
        Returns:
            CalibrationCape object with extracted calibration data.

        """
        dv = cls().model_dump(include={"harvester", "emulator"})
        lw1 = list(dict_generator(dv))
        lw2 = [elem for elem in lw1 if isinstance(elem[-1], float)]
        values = struct.unpack(">" + len(lw2) * "d", data)
        # ⤷ X => double float, big endian
        for _i, walk in enumerate(lw2):
            # hardcoded fixed depth ... bad but easy
            dv[walk[0]][walk[1]][walk[2]] = float(values[_i])
        dv["cape"] = cape
        return cls(**dv)

    def to_bytestr(self) -> bytes:
        """Serialize calibration data to byte string.

        Used to prepare data for writing it to EEPROM.

        Returns:
            Byte string representation of calibration values.

        """
        lw = list(dict_generator(self.model_dump(include={"harvester", "emulator"})))
        values = [walk[-1] for walk in lw if isinstance(walk[-1], float)]
        return struct.pack(">" + len(values) * "d", *values)


class CalibrationSeries(ShpModel):
    """Cal-Data for a typical recording of a testbed experiment."""

    voltage: CalibrationPair = CalibrationPair(gain=3 * 1e-9, unit="V")
    # ⤷ default allows 0 - 12 V in 3 nV-Steps
    current: CalibrationPair = CalibrationPair(gain=250 * 1e-12, unit="A")
    # ⤷ default allows 0 - 1 A in 250 pA - Steps
    time: CalibrationPair = CalibrationPair(gain=1e-9, unit="s")
    # ⤷ default = nanoseconds

    @classmethod
    @validate_call(validate_return=False)
    def from_cal(
        cls,
        cal: Union[CalibrationHarvester, CalibrationEmulator],
        *,
        emu_port_a: bool = True,
    ) -> Self:
        if isinstance(cal, CalibrationHarvester):
            return cls(voltage=cal.adc_V_Sense, current=cal.adc_C_Hrv)
        if emu_port_a:
            return cls(voltage=cal.dac_V_A, current=cal.adc_C_A)
        return cls(voltage=cal.dac_V_B, current=cal.adc_C_B)
