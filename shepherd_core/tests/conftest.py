import subprocess
from collections.abc import Iterable
from pathlib import Path

import numpy as np
import pytest

from shepherd_core import Writer


def generate_h5_file(file_path: Path, file_name: str = "harvest_example.h5") -> Path:
    store_path = file_path / file_name

    with Writer(store_path) as file:
        file.store_hostname("artificial")

        duration_s = 2
        repetitions = 5
        timestamp_vector = np.arange(0.0, duration_s, file.sample_interval_ns / 1e9)

        # values in SI units
        voltages = np.linspace(3.60, 1.90, int(file.samplerate_sps * duration_s))
        currents = np.linspace(100e-6, 2000e-6, int(file.samplerate_sps * duration_s))

        for idx in range(repetitions):
            timestamps = idx * duration_s + timestamp_vector
            file.append_iv_data_si(timestamps, voltages, currents)

    return store_path


@pytest.fixture
def data_h5(tmp_path: Path) -> Path:
    return generate_h5_file(tmp_path)


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: Iterable[pytest.Item],
) -> None:
    # ELF
    try:
        from pwnlib.elf import ELF
    except ImportError:
        ELF = None
    skip_elf = pytest.mark.skip(
        reason="ELF-support not found -> shepherd_core[elf] missing or OS is Windows?"
    )

    # OBJCOPY
    try:
        subprocess.run(["objcopy", "--version"], check=True)
        OBJCOPY = True
    except FileNotFoundError:
        OBJCOPY = None
    skip_converter = pytest.mark.skip(
        reason="Objcopy not found -> are binutils or build-essential installed?"
    )

    for item in items:
        if "elf" in item.keywords and ELF is None:
            item.add_marker(skip_elf)
        if "converter" in item.keywords and OBJCOPY is None:
            item.add_marker(skip_converter)
