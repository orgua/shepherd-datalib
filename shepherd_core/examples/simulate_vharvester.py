"""Demonstrate behavior of Virtual Harvester Algorithms.

- simulation is based on ivsamples derived from a solar-isc-voc-recording during a jogging-trip
- harvesting is done by various algorithms and preconfigured virtual harvesters
- results are printed on console (harvested energy)

Output:
E_out = 0.000 mWs -> cv20
E_out = 17.165 mWs -> cv10
E_out = 17.427 mWs -> mppt_voc
E_out = 17.242 mWs -> mppt_bq_solar
E_out = 13.998 mWs -> mppt_bq_thermoelectric
E_out = 15.202 mWs -> mppt_po
E_out = 17.811 mWs -> mppt_opt
"""

from pathlib import Path

from shepherd_core import Reader
from shepherd_core.data_models import VirtualHarvesterConfig
from shepherd_core.vsource import simulate_harvester
from shepherd_data import ivonne

# config simulation
sim_duration = 32
file_ivonne = Path(__file__).parent.parent.parent / "shepherd_data/examples/jogging_10m.iv"
file_ivcurve = Path(__file__).parent / "jogging_ivcurve.h5"

hrv_list = [
    "cv20",
    # ⤷ fails due to lower solar voltage
    "cv10",
    "mppt_voc",
    "mppt_bq_solar",
    # ⤷ bq needs 16 s to start -> bad performance for this demo
    "mppt_bq_thermoelectric",
    # ⤷ thermoelectric setpoint -> bad performance for solar
    "mppt_po",
    "mppt_opt",
]

save_files: bool = False

# convert IVonne to IVCurve
if not file_ivcurve.exists():
    with ivonne.Reader(file_ivonne) as db:
        db.convert_2_ivcurves(file_ivcurve, duration_s=sim_duration)

# Input Statistics
with Reader(file_ivcurve, verbose=False) as file:
    window_size = file.get_window_samples()
    I_in_max = 0.0
    for _t, _v, _i in file.read_buffers():
        I_in_max = max(I_in_max, _i.max())
    print(
        f"Input-file: \n"
        f"\tE_in = {file.energy() * 1e3:.3f} mWs (not representative)\n"
        f"\tI_in_max = {I_in_max * 1e3:.3f} mA\n"
        f"\twindow_size = {window_size} n\n",
    )

# Simulation
for hrv_name in hrv_list:
    file_output = file_ivcurve.with_stem(file_ivcurve.stem + "_" + hrv_name) if save_files else None
    E_out_Ws = simulate_harvester(
        config=VirtualHarvesterConfig(name=hrv_name),
        path_input=file_ivcurve,
        path_output=file_output,
    )
    print(f"E_out = {E_out_Ws * 1e3:.3f} mWs -> {hrv_name}")
