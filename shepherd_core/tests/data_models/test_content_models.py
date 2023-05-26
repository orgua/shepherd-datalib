import pytest
from pydantic import ValidationError

from shepherd_core.data_models.content import EnergyDType
from shepherd_core.data_models.content import EnergyEnvironment
from shepherd_core.data_models.content import Firmware
from shepherd_core.data_models.content import FirmwareDType
from shepherd_core.data_models.content import VirtualHarvester
from shepherd_core.data_models.content import VirtualSource
from shepherd_core.data_models.content.virtual_source import VirtualSourcePRU
from shepherd_core.data_models.testbed import MCU


def test_content_model_ee_min1() -> None:
    EnergyEnvironment(
        id=9999,
        name="some",
        data_path="./file",
        data_type="isc_voc",
        duration=1,
        energy_Ws=0.1,
        owner="jane",
        group="wayne",
    )


def test_content_model_ee_min2() -> None:
    EnergyEnvironment(
        id="98765",
        name="some",
        data_path="./file",
        data_type=EnergyDType.ivcurve,
        duration=999,
        energy_Ws=3.1,
        owner="jane",
        group="wayne",
    )


def test_content_model_fw_min() -> None:
    Firmware(
        id=9999,
        name="dome",
        mcu=MCU(name="nRF52"),
        data="xyz",
        data_type=FirmwareDType.base64_hex,
        owner="Obelix",
        group="Gaul",
    )


def test_content_model_hrv_min() -> None:
    hrv = VirtualHarvester(
        id=9999,
        name="whatever",
        owner="jane",
        group="wayne",
        algorithm="mppt_opt",
    )
    assert hrv.get_datatype() == "ivsample"


def test_content_model_hrv_neutral() -> None:
    with pytest.raises(ValueError):
        _ = VirtualHarvester(name="neutral")


@pytest.mark.parametrize("name", ["iv110", "cv24", "mppt_voc", "mppt_po"])
def test_content_model_hrv_by_name(name: str) -> None:
    _ = VirtualHarvester(name=name)


@pytest.mark.parametrize("uid", [1013, 1020, 1032, 1044, 1045, 1046])
def test_content_model_hrv_by_id(uid: int) -> None:
    _ = VirtualHarvester(id=uid)


def test_content_model_hrv_steps() -> None:
    hrv = VirtualHarvester(
        name="ivcurves", voltage_min_mV=1000, voltage_max_mV=4000, samples_n=11
    )
    assert hrv.voltage_step_mV == 300


def test_content_model_hrv_faulty_voltage0() -> None:
    with pytest.raises(ValidationError):
        _ = VirtualHarvester(name="iv110", voltage_max_mV=5001)
    with pytest.raises(ValidationError):
        _ = VirtualHarvester(name="iv110", voltage_min_mV=-1)


def test_content_model_hrv_faulty_voltage1() -> None:
    with pytest.raises(ValueError):
        _ = VirtualHarvester(name="iv110", voltage_min_mV=4001, voltage_max_mV=4000)


def test_content_model_hrv_faulty_voltage2() -> None:
    with pytest.raises(ValueError):
        _ = VirtualHarvester(name="iv110", voltage_mV=4001, voltage_max_mV=4000)


def test_content_model_hrv_faulty_voltage3() -> None:
    with pytest.raises(ValueError):
        _ = VirtualHarvester(name="iv110", voltage_mV=4000, voltage_min_mV=4001)


@pytest.mark.parametrize("name", ["ivcurves", "iv1000", "isc_voc"])
def test_content_model_hrv_faulty_emu(name: str) -> None:
    hrv = VirtualHarvester(name=name)
    with pytest.raises(ValueError):
        _ = VirtualSource(name="dio_cap", harvester=hrv)


def test_content_model_src_min() -> None:
    VirtualSource(
        id=9999,
        name="new_src",
        owner="jane",
        group="wayne",
    )


def test_content_model_src_force_warning() -> None:
    src = VirtualSource(
        name="BQ25570",
        C_output_uF=200,
        C_intermediate_uF=100,
    )
    VirtualSourcePRU.from_vsrc(src)
    # -> triggers warning currently


def test_content_model_src_force_other_hysteresis1() -> None:
    src = VirtualSource(
        name="BQ25570",
        V_intermediate_enable_threshold_mV=4000,
        V_intermediate_disable_threshold_mV=3999,
        V_output_mV=2000,
        V_buck_drop_mV=100,
    )
    VirtualSourcePRU.from_vsrc(src)


def test_content_model_src_force_other_hysteresis2() -> None:
    src = VirtualSource(
        name="BQ25570",
        V_intermediate_enable_threshold_mV=1000,
        V_intermediate_disable_threshold_mV=999,
        V_output_mV=2000,
        V_buck_drop_mV=100,
    )
    VirtualSourcePRU.from_vsrc(src)
