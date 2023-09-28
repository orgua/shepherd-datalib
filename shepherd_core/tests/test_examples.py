import os
import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def example_path() -> Path:
    path = Path(__file__).resolve().parent.parent / "examples"
    os.chdir(path)
    return path


examples = [
    "experiment_generic.py",
    "experiment_models.py",
    "firmware_model.py",
    "firmware_modification.py",
    "inventory.py",
    "uart_decode_waveform.py",
    "vharvester_simulation.py",
    "vsource_simulation.py",
]


@pytest.mark.parametrize("file", examples)
def test_example_scripts(example_path: Path, file: str) -> None:
    subprocess.check_call(f"python {example_path / file}", shell=True)
