"""Generalized energy harvester data models."""

from enum import Enum
from typing import Annotated
from typing import Optional

from pydantic import Field
from pydantic import model_validator
from typing_extensions import Self

from ...commons import samplerate_sps_default
from ...logger import logger
from ...testbed_client import tb_client
from ..base.calibration import CalibrationHarvester
from ..base.content import ContentModel
from ..base.shepherd import ShpModel
from .energy_environment import EnergyDType


class AlgorithmDType(str, Enum):
    """Options for choosing a harvesting algorithm."""

    direct = disable = neutral = "neutral"
    isc_voc = "isc_voc"
    ivcurve = ivcurves = ("ivcurve",)
    constant = cv = "cv"
    # ci .. constant current -> is this desired?
    mppt_voc = "mppt_voc"
    mppt_po = perturb_observe = "mppt_po"
    mppt_opt = optimal = "mppt_opt"


class VirtualHarvesterConfig(ContentModel, title="Config for the Harvester"):
    """A vHrv makes a source-characterization (i.e. ivcurve) usable for the vSrc.

    Mostly used when the file-based energy environment of the virtual source
    is not already supplied as pre-harvested ivsample-stream.
    """

    # General Metadata & Ownership -> ContentModel

    algorithm: AlgorithmDType
    # ⤷ used to harvest energy

    samples_n: Annotated[int, Field(ge=8, le=2_000)] = 8
    # ⤷ for & of ivcurve (and more?`)

    voltage_mV: Annotated[float, Field(ge=0, le=5_000)] = 2_500
    # ⤷ starting-point for some algorithms (mppt_po)
    voltage_min_mV: Annotated[float, Field(ge=0, le=5_000)] = 0
    voltage_max_mV: Annotated[float, Field(ge=0, le=5_000)] = 5_000
    current_limit_uA: Annotated[float, Field(ge=1, le=50_000)] = 50_000
    # ⤷ allows to keep trajectory in special region (or constant current tracking)
    # ⤷ boundary for detecting open circuit in emulated version (working on IV-Curves)
    voltage_step_mV: Optional[Annotated[float, Field(ge=1, le=1_000_000)]] = None

    setpoint_n: Annotated[float, Field(ge=0, le=1.0)] = 0.70
    # ⤷ ie. for mppt_voc
    interval_ms: Annotated[float, Field(ge=0.01, le=1_000_000)] = 100
    # ⤷ between start of measurements (ie. V_OC)
    duration_ms: Annotated[float, Field(ge=0.01, le=1_000_000)] = 0.1
    # ⤷ of (open voltage) measurement
    rising: bool = True
    # ⤷ direction of sawtooth
    enable_linear_extrapolation: bool = True
    # ⤷ improves slow cv-algo that is base of most ivcurve-harvesters
    #   (update-freq dependent on window-size)

    # Underlying recorder
    wait_cycles: Annotated[int, Field(ge=0, le=100)] = 1
    # ⤷ first cycle: ADC-Sampling & DAC-Writing, further steps: waiting

    @model_validator(mode="before")
    @classmethod
    def query_database(cls, values: dict) -> dict:
        values, chain = tb_client.try_completing_model(cls.__name__, values)
        values = tb_client.fill_in_user_data(values)
        if values["name"] == "neutral":
            # TODO: same test is later done in calc_algorithm_num() again
            raise ValueError("Resulting Harvester can't be neutral")
        logger.debug("VHrv-Inheritances: %s", chain)

        # post corrections -> should be in separate validator
        cal = CalibrationHarvester()  # TODO: as argument?
        c_limit = values.get("current_limit_uA", 50_000)  # cls.current_limit_uA)
        values["current_limit_uA"] = max(10**6 * cal.adc_C_Hrv.raw_to_si(4), c_limit)

        if values.get("voltage_step_mV") is None:
            # algo includes min & max!
            v_max = values.get("voltage_max_mV", 5_000)  # cls.voltage_max_mV)
            v_min = values.get("voltage_min_mV", 0)  # cls.voltage_min_mV)
            samples_n = values.get("samples_n", 8)  # cls.samples_n) TODO
            values["voltage_step_mV"] = abs(v_max - v_min) / (samples_n - 1)

        values["voltage_step_mV"] = max(
            10**3 * cal.dac_V_Hrv.raw_to_si(4), values["voltage_step_mV"]
        )

        return values

    @model_validator(mode="after")
    def post_validation(self) -> Self:
        if self.voltage_min_mV > self.voltage_max_mV:
            raise ValueError("Voltage min > max")
        if self.voltage_mV < self.voltage_min_mV:
            raise ValueError("Voltage below min")
        if self.voltage_mV > self.voltage_max_mV:
            raise ValueError("Voltage above max")

        return self

    def calc_hrv_mode(self, *, for_emu: bool) -> int:
        return 1 * int(for_emu) + 2 * self.rising + 4 * self.enable_linear_extrapolation

    def calc_algorithm_num(self, *, for_emu: bool) -> int:
        num = algo_to_num.get(self.algorithm)
        if for_emu and self.get_datatype() != EnergyDType.ivsample:
            msg = (
                f"[{self.name}] Select valid harvest-algorithm for emulator, "
                f"current usage = {self.algorithm}"
            )
            raise ValueError(msg)
        if not for_emu and num < algo_to_num["isc_voc"]:
            msg = (
                f"[{self.name}] Select valid harvest-algorithm for harvester, "
                f"current usage = {self.algorithm}"
            )
            raise ValueError(msg)
        return num

    def calc_timings_ms(self, *, for_emu: bool) -> tuple[float, float]:
        """factor-in model-internal timing-constraints."""
        window_length = self.samples_n * (1 + self.wait_cycles)
        time_min_ms = (1 + self.wait_cycles) * 1_000 / samplerate_sps_default
        if for_emu:
            window_ms = window_length * 1_000 / samplerate_sps_default
            time_min_ms = max(time_min_ms, window_ms)

        interval_ms = min(max(self.interval_ms, time_min_ms), 1_000_000)
        duration_ms = min(max(self.duration_ms, time_min_ms), interval_ms)
        _ratio = (duration_ms / interval_ms) / (self.duration_ms / self.interval_ms)
        if (_ratio - 1) > 0.1:
            logger.debug(
                "Ratio between interval & duration has changed "
                "more than 10%% due to constraints (%.4f)",
                _ratio,
            )
        return interval_ms, duration_ms

    def get_datatype(self) -> EnergyDType:
        return algo_to_dtype[self.algorithm]

    def calc_window_size(
        self,
        dtype_in: Optional[EnergyDType] = None,
        *,
        for_emu: bool,
    ) -> int:
        if not for_emu:
            # TODO: should be named 'for_ivcurve_recording'
            # TODO: add extra variable to distinguish step_count
            #       and window_size (currently mixed together)
            # only used by ivcurve algo (in ADC-Mode)
            return self.samples_n

        if dtype_in is None:
            dtype_in = self.get_datatype()

        if dtype_in == EnergyDType.ivcurve:
            return self.samples_n * (1 + self.wait_cycles)
        if dtype_in == EnergyDType.ivsample:
            return 0
        if dtype_in == EnergyDType.isc_voc:
            return 2 * (1 + self.wait_cycles)
        raise NotImplementedError


u32 = Annotated[int, Field(ge=0, lt=2**32)]


# Currently implemented harvesters
# NOTE: numbers have meaning and will be tested ->
# - harvesting on "neutral" is not possible - direct pass-through
# - emulation with "ivcurve" or lower is also resulting in Error
# - "_opt" has its own algo for emulation, but is only a fast mppt_po for harvesting
algo_to_num = {
    "neutral": 2**0,
    "isc_voc": 2**3,
    "ivcurve": 2**4,
    "cv": 2**8,
    # is "ci" desired?
    "mppt_voc": 2**12,
    "mppt_po": 2**13,
    "mppt_opt": 2**14,
}

algo_to_dtype = {
    "neutral": EnergyDType.ivsample,
    "isc_voc": EnergyDType.isc_voc,
    "ivcurve": EnergyDType.ivcurve,
    "cv": EnergyDType.ivsample,
    "mppt_voc": EnergyDType.ivsample,
    "mppt_po": EnergyDType.ivsample,
    "mppt_opt": EnergyDType.ivsample,
}


class HarvesterPRUConfig(ShpModel):
    """Map settings-list to internal state-vars struct HarvesterConfig for PRU.

    NOTE:
      - yaml is based on si-units like nA, mV, ms, uF
      - c-code and py-copy is using nA, uV, ns, nF, fW, raw
      - ordering is intentional and in sync with shepherd/commons.h.
    """

    algorithm: u32
    hrv_mode: u32
    window_size: u32
    voltage_uV: u32
    voltage_min_uV: u32
    voltage_max_uV: u32
    voltage_step_uV: u32
    # ⤷ for window-based algo like ivcurve
    current_limit_nA: u32
    # ⤷ lower bound to detect zero current
    setpoint_n8: u32
    interval_n: u32
    # ⤷ between measurements
    duration_n: u32
    # ⤷ of measurement
    wait_cycles_n: u32
    # ⤷ for DAC to settle

    @classmethod
    def from_vhrv(
        cls,
        data: VirtualHarvesterConfig,
        dtype_in: Optional[EnergyDType] = EnergyDType.ivsample,
        window_size: Optional[u32] = None,
        voltage_step_V: Optional[float] = None,
        *,
        for_emu: bool = False,
    ) -> Self:
        if isinstance(dtype_in, str):
            dtype_in = EnergyDType[dtype_in]
        if for_emu and dtype_in not in {EnergyDType.ivsample, EnergyDType.ivcurve}:
            raise NotImplementedError

        if for_emu and dtype_in == EnergyDType.ivcurve and voltage_step_V is None:
            raise ValueError(
                "For correct emulation specify voltage_step used by harvester "
                "e.g. via file_src.get_voltage_step()"
            )

        if for_emu and dtype_in == EnergyDType.ivcurve and window_size is None:
            raise ValueError(
                "For correct emulation specify window_size used by harvester "
                "e.g. via file_src.get_window_size()"
            )

        interval_ms, duration_ms = data.calc_timings_ms(for_emu=for_emu)
        window_size = (
            window_size
            if window_size is not None
            else data.calc_window_size(dtype_in, for_emu=for_emu)
        )
        voltage_step_mV = (
            1e3 * voltage_step_V if voltage_step_V is not None else data.voltage_step_mV
        )

        return cls(
            algorithm=data.calc_algorithm_num(for_emu=for_emu),
            hrv_mode=data.calc_hrv_mode(for_emu=for_emu),
            window_size=window_size,
            voltage_uV=round(data.voltage_mV * 10**3),
            voltage_min_uV=round(data.voltage_min_mV * 10**3),
            voltage_max_uV=round(data.voltage_max_mV * 10**3),
            voltage_step_uV=round(voltage_step_mV * 10**3),
            current_limit_nA=round(data.current_limit_uA * 10**3),
            setpoint_n8=round(min(255, data.setpoint_n * 2**8)),
            interval_n=round(interval_ms * samplerate_sps_default * 1e-3),
            duration_n=round(duration_ms * samplerate_sps_default * 1e-3),
            wait_cycles_n=data.wait_cycles,
        )
