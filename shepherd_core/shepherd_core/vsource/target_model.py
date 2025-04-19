"""Virtual targets with different characteristics.

TODO: add more targets
  - diode
  - constant power
  - constant current
  - msp430 (const I)
  - nRF (constant power due to regulator)
  - riotee
"""

import math
from abc import ABC
from abc import abstractmethod
from contextlib import suppress


class TargetABC(ABC):
    """Abstract base class for all targets."""

    @abstractmethod
    def step(self, voltage_uV: int, *, pwr_good: bool) -> float:
        """Calculate one time step and return drawn current in nA."""


class ResistiveTarget(TargetABC):
    """Predictable target with linear behavior."""

    def __init__(self, R_Ohm: float, *, controlled: bool = False) -> None:
        if R_Ohm <= 1e-3:
            raise ValueError("Resistance must be greater than 1 mOhm.")
        self.R_kOhm = 1e-3 * R_Ohm
        self.ctrl = controlled

    def step(self, voltage_uV: int, *, pwr_good: bool) -> float:
        if pwr_good or not self.ctrl:
            return voltage_uV / self.R_kOhm  # = nA
        return 0


class DiodeTarget(TargetABC):
    """Emulate a diode and current limiting resistor in series.

    Good for modeling a debug-diode that burns energy.
    It uses Shockley Diode Equation to estimate a model for diode
    I_D = I_S * ( e ^ ( U_D / n*U_T ) - 1 )

    diode of shepherd target:
    d1 = DiodeTarget(V_forward_V = 2.0, I_forward_A = 20e-3, R_Ohm = 100)

    """

    def __init__(
        self,
        V_forward_V: float,
        I_forward_A: float,
        R_Ohm: float,
        *,
        controlled: bool = False,
    ) -> None:
        if R_Ohm <= 1e-3:
            raise ValueError("Resistance must be greater than 1 mOhm.")
        if V_forward_V <= 0.2:
            raise ValueError("Forward-Voltage of diode must be greater than 200 mV.")
        if I_forward_A <= 0:
            raise ValueError("Forward-current of diode must be greater than 0 A.")

        k = 1.380649e-23  # boltzmann
        q = 1.6021766e-19  # elementary charge
        TJ = 100 + 273.15  # junction temperature

        V_T = k * TJ / q  # thermal voltage
        n = 2  # ideality factor
        self.c1 = V_T * n
        # NOTE: math.expm1(x) = math.exp(x) - 1 = e^x -1
        self.I_S = I_forward_A / math.expm1(V_forward_V / self.c1)  # scale current
        self.R_Ohm = R_Ohm
        self.ctrl = controlled

    def step(self, voltage_uV: int, *, pwr_good: bool) -> float:
        if pwr_good or not self.ctrl:
            V_CC: float = voltage_uV * 1e-6
            V_D: float = V_CC / 2
            I_R = I_D = 0.0
            # there is no direct formular, but this iteration converges fast
            for _ in range(10):
                # low voltages tend to produce log(x<0)=err
                with suppress(ValueError):
                    V_D = self.c1 * math.log(1 + (V_CC - V_D) / (self.R_Ohm * self.I_S))
                # both currents are positive and should be identical
                I_R = max(0.0, (V_CC - V_D) / self.R_Ohm)
                I_D = max(0.0, self.I_S * math.expm1(V_D / self.c1))
                with suppress(ZeroDivisionError):
                    if abs(I_R / I_D - 1) < 1e-6:
                        break
                # take mean of both currents and determine a new V_D
                V_D = V_CC - self.R_Ohm * (I_R + I_D) / 2
            return 1e9 * (I_R + I_D) / 2  # = nA
        return 0


class ConstantCurrentTarget(TargetABC):
    """Recreate simple MCU without integrated regulator, i.e. msp430."""

    def __init__(self, I_active_A: float, I_sleep_A: float = 0) -> None:
        if I_active_A <= 0 or I_sleep_A < 0:
            raise ValueError("Current must be greater than 0.")
        self.I_active_nA = 1e9 * I_active_A
        self.I_sleep_nA = 1e9 * I_sleep_A

    def step(self, voltage_uV: int, *, pwr_good: bool) -> float:  # noqa: ARG002
        return self.I_active_nA if pwr_good else self.I_sleep_nA


class ConstantPowerTarget(TargetABC):
    """Recreate MCU with integrated regulator, i.e. nRF52."""

    def __init__(self, P_active_W: float, P_sleep_W: float = 0) -> None:
        if P_active_W <= 0 or P_sleep_W < 0:
            raise ValueError("Power must be greater than 0.")
        self.P_active_fW = 1e15 * P_active_W
        self.P_sleep_fW = 1e15 * P_sleep_W

    def step(self, voltage_uV: int, *, pwr_good: bool) -> float:
        return (self.P_active_fW if pwr_good else self.P_sleep_fW) / voltage_uV  # = nA


# exemplary instantiations

diode_target_burn = DiodeTarget(V_forward_V=2.0, I_forward_A=20e-3, R_Ohm=100)
mcu_msp430fr = ConstantCurrentTarget(I_active_A=16 * 118e-6, I_sleep_A=350e-9)
mcu_msp_deep_sleep = ConstantCurrentTarget(45e-9, 45e-9)
# TODO: writing FRAM
mcu_nrf52840 = ConstantPowerTarget(P_active_W=3 * 3e-3, P_sleep_W=3 * 0.97e-6)
mcu_nrf_tx_8dBm = ConstantPowerTarget(P_active_W=3.0 * 16.40e-3)
mcu_nrf_tx_0dBm = ConstantPowerTarget(P_active_W=3.0 * 6.40e-3)
mcu_nrf_rx = ConstantPowerTarget(P_active_W=3.0 * 6.26e-3)
# data based on PS1.10
# - TX 8 dBm -> 6.31 mW -> DS shows 16.40 mA @ 3V (DC/DC)
# - TX 0 dBm -> 1 mW ->              6.40 mA
# - RX ->                            6.26 mA
