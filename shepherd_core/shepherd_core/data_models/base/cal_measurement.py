from typing import Optional

import numpy as np
from pydantic import PositiveFloat
from pydantic import conlist
from pydantic import validate_arguments
from scipy.stats import stats

from ...logger import logger
from .. import CalibrationCape
from .. import CalibrationEmulator
from .. import CalibrationHarvester
from .. import CalibrationPair
from .shepherd import ShpModel

# TODO: port over TESTs


class CalMeasurementPair(ShpModel):
    shepherd_raw: PositiveFloat
    reference_si: float = 0


CalMeasPairs = conlist(item_type=CalMeasurementPair, min_items=2)


@validate_arguments
def meas_to_cal(
    data: CalMeasPairs, default: CalibrationPair, component: str
) -> CalibrationPair:
    gain = default.gain
    offset = default.offset
    rval = 0
    try:
        x = np.empty(len(data))
        y = np.empty(len(data))
        for i, pair in enumerate(data):
            x[i] = pair.shepherd_raw
            y[i] = pair.reference_si
        result = stats.linregress(x, y)
        offset = float(result.intercept)
        gain = float(result.slope)
        rval = result.rvalue  # test quality of regression
    except KeyError:
        logger.error(
            "data not found in '%s' -> fallback to default (gain=%f)",
            component,
            gain,
        )
    except ValueError:
        logger.error(
            "data not found in '%s' -> fallback to default (gain=%f)",
            component,
            gain,
        )

    if rval < 0.999:
        raise ValueError(
            "Calibration faulty -> Correlation coefficient "
            f"(rvalue) = {rval}:.6f is too low for '{component}'"
        )
    return CalibrationPair(offset=offset, gain=gain)


class CalMeasurementHarvester(ShpModel):
    dac_V_Hrv: CalMeasPairs
    dac_V_Sim: CalMeasPairs
    adc_V_Sense: CalMeasPairs
    adc_C_Hrv: CalMeasPairs

    def to_cal(self) -> CalibrationHarvester:
        dv = self.dict()
        dcal = CalibrationHarvester().dict()
        for key, value in dv.items():
            dcal[key] = meas_to_cal(value, dcal[key], f"hrv_{key}")
        return CalibrationHarvester(**dcal)


class CalMeasurementEmulator(ShpModel):
    dac_V_Main: CalMeasPairs
    dac_V_Aux: CalMeasPairs
    adc_C_A: CalMeasPairs
    adc_C_B: CalMeasPairs

    def to_cal(self) -> CalibrationEmulator:
        dv = self.dict()
        dcal = CalibrationEmulator().dict()
        for key, value in dv.items():
            dcal[key] = meas_to_cal(value, dcal[key], f"emu_{key}")
        return CalibrationEmulator(**dcal)


class CalMeasurementCape(ShpModel):
    harvester: Optional[CalMeasurementHarvester]
    emulator: Optional[CalMeasurementEmulator]

    def to_cal(self) -> CalibrationCape:
        dv = self.dict()
        dcal = CalibrationCape().dict()
        for key, value in dv.items():
            if value is not None:
                dcal[key] = value.to_cal()
        return CalibrationCape(**dcal)