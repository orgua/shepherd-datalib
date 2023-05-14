from shepherd_core.data_models.content.energy_environment import EnergyEnvironment
from shepherd_core.data_models.content.energy_environment import fixtures as fix_ee
from shepherd_core.data_models.content.firmware import Firmware
from shepherd_core.data_models.content.firmware import fixtures as fix_firmware
from shepherd_core.data_models.content.virtual_harvester import VirtualHarvester
from shepherd_core.data_models.content.virtual_harvester import VirtualHarvesterPRU
from shepherd_core.data_models.content.virtual_harvester import fixtures as fix_hrv
from shepherd_core.data_models.content.virtual_source import VirtualSource
from shepherd_core.data_models.content.virtual_source import VirtualSourcePRU
from shepherd_core.data_models.content.virtual_source import fixtures as fix_src


def test_testbed_fixture_energy_environment():
    for fix in fix_ee:
        EnergyEnvironment(name=fix["name"])
        EnergyEnvironment(id=fix["id"])


def test_testbed_fixture_firmware():
    for fix in fix_firmware:
        _id = fix["id"]
        if _id in [1001, 1002]:
            continue
        Firmware(name=fix["name"])
        Firmware(id=fix["id"])


def test_experiment_fixture_vsrc():
    for fix in fix_src:
        vsrc = VirtualSource(name=fix["name"])
        VirtualSource(id=fix["id"])
        VirtualSourcePRU.from_vsrc(vsrc, log_intermediate_node=False)
        VirtualSourcePRU.from_vsrc(vsrc, log_intermediate_node=True)


def test_experiment_fixture_vhrv():
    for fix in fix_hrv:
        if fix["name"] == "neutral":
            continue
        vhrv = VirtualHarvester(name=fix["name"])
        VirtualHarvester(id=fix["id"])
        VirtualHarvesterPRU.from_vhrv(vhrv, for_emu=False)
        if int(fix["id"]) >= 1030:
            VirtualHarvesterPRU.from_vhrv(vhrv, for_emu=True)
