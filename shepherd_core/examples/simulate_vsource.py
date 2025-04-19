"""Demonstrate behavior of Virtual Source Algorithms.

The emulation recreates an observer-cape, the virtual Source and a virtual target
- input = hdf5-file with a harvest-recording
- output = hdf5-file
- config is currently hardcoded, but it could be an emulation-task
- target is currently a simple resistor

The output file can be analyzed and plotted with shepherds tool suite.

Output:
E_out = 220.001 mWs -> direct (no current-limit)
E_out = 13.142 mWs -> diode+capacitor
E_out = 13.066 mWs -> diode+resistor+capacitor
E_out = 15.045 mWs -> BQ25504
E_out = 14.962 mWs -> BQ25504s
E_out = 14.397 mWs -> BQ25570
E_out = 14.232 mWs -> BQ25570s

"""

from pathlib import Path

from shepherd_core.data_models import VirtualSourceConfig
from shepherd_core.vsource import ResistiveTarget
from shepherd_core.vsource import simulate_source
from shepherd_data import Reader

# config simulation
file_input = Path(__file__).parent / "jogging_ivcurve.h5"

src_list = [
    "direct",
    "diode+capacitor",
    "diode+resistor+capacitor",
    "BQ25504",
    "BQ25504s",
    "BQ25570",
    "BQ25570s",
]
tgt = ResistiveTarget(R_Ohm=1_000, controlled=True)
save_files = True

for src_name in src_list:
    file_output = file_input.with_stem(file_input.stem + "_emu_" + src_name) if save_files else None

    e_out_Ws = simulate_source(
        config=VirtualSourceConfig(
            name=src_name,
            C_output_uF=0,
            V_intermediate_enable_threshold_mV=1,
            V_intermediate_disable_threshold_mV=0,
            # jogging-dataset has max VOC of ~1.6 V -> lower set-point for non-boost
            C_intermediate_uF=100 if "direct" not in src_name else 0,
            V_pwr_good_enable_threshold_mV=1300 if "dio" in src_name else 2800,
            V_pwr_good_disable_threshold_mV=1000 if "dio" in src_name else 2400,
            V_input_drop_mV=150 if "dio" in src_name else 0,
        ),
        target=tgt,
        path_input=file_input,
        path_output=file_output,
        monitor_internals=True,
    )
    print(f"E_out = {e_out_Ws * 1e3:.3f} mWs -> {src_name}")

    with Reader(file_output, verbose=False) as reader:
        reader.plot_to_file()
        reader.plot_to_file(start_s=1, end_s=1.1)
