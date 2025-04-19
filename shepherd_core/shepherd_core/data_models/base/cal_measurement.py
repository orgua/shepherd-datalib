"""Models for the process of calibration a device by measurements."""

from typing import Annotated
from typing import Optional

import numpy as np
from pydantic import Field
from pydantic import PositiveFloat
from pydantic import validate_call

from .calibration import CalibrationCape
from .calibration import CalibrationEmulator
from .calibration import CalibrationHarvester
from .calibration import CalibrationPair
from .calibration import CapeData
from .shepherd import ShpModel


class CalMeasurementPair(ShpModel):
    """Value-container for a calibration-measurement."""

    shepherd_raw: PositiveFloat
    reference_si: float = 0


CalMeasPairs = Annotated[list[CalMeasurementPair], Field(min_length=2)]


@validate_call
def meas_to_cal(data: CalMeasPairs, component: str) -> CalibrationPair:
    """Convert values from calibration-measurement to the calibration itself."""
    x = np.empty(len(data))
    y = np.empty(len(data))
    for i, pair in enumerate(data):
        x[i] = pair.shepherd_raw
        y[i] = pair.reference_si

    model = np.polyfit(x, y, 1)
    offset: float = float(model[1])
    gain: float = float(model[0])

    # r-squared, Pearson correlation coefficient
    _p = np.poly1d(model)
    yhat = _p(x)
    ybar: float = np.sum(y) / len(y)
    ssreg: float = np.sum((yhat - ybar) ** 2)
    sstot: float = np.sum((y - ybar) ** 2)
    rval: float = ssreg / sstot

    if rval < 0.999:
        msg = (
            "Calibration faulty -> Correlation coefficient "
            f"(rvalue) = {rval}:.6f is too low for '{component}'"
        )
        raise ValueError(msg)
    return CalibrationPair(offset=offset, gain=gain)


class CalMeasurementHarvester(ShpModel):
    """Container for the values of the calibration-measurement."""

    dac_V_Hrv: CalMeasPairs
    dac_V_Sim: CalMeasPairs
    adc_V_Sense: CalMeasPairs
    adc_C_Hrv: CalMeasPairs

    def to_cal(self) -> CalibrationHarvester:
        dv = self.model_dump()
        dcal = CalibrationHarvester().model_dump()
        for key in dv:
            dcal[key] = meas_to_cal(self[key], f"hrv_{key}")
        return CalibrationHarvester(**dcal)


class CalMeasurementEmulator(ShpModel):
    """Container for the values of the calibration-measurement."""

    dac_V_A: CalMeasPairs  # TODO: why not V_dac_A or V_dac_a
    dac_V_B: CalMeasPairs
    adc_C_A: CalMeasPairs
    adc_C_B: CalMeasPairs

    def to_cal(self) -> CalibrationEmulator:
        dv = self.model_dump()
        dcal = CalibrationEmulator().model_dump()
        for key in dv:
            dcal[key] = meas_to_cal(self[key], f"emu_{key}")
        return CalibrationEmulator(**dcal)


class CalMeasurementCape(ShpModel):
    """Container for the values of the calibration-measurement."""

    cape: Optional[CapeData] = None
    host: Optional[str] = None

    harvester: Optional[CalMeasurementHarvester] = None
    emulator: Optional[CalMeasurementEmulator] = None

    def to_cal(self) -> CalibrationCape:
        dv = self.model_dump()
        dcal = CalibrationCape().model_dump()
        # TODO: is it helpful to default wrong / missing values?
        for key, value in dv.items():
            if key in {"harvester", "emulator"}:
                if value is not None:
                    dcal[key] = self[key].to_cal()
            else:
                dcal[key] = self[key]

        return CalibrationCape(**dcal)
