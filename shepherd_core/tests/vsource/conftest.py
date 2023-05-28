import os
from pathlib import Path

import pytest

from shepherd_data import ivonne
from shepherd_data import mppt


@pytest.fixture
def file_ivonne() -> Path:
    path = (
        Path(__file__).absolute().parent.parent.parent.parent / "shepherd_data/examples"
    )
    os.chdir(path)
    return path / "./jogging_10m.iv"


@pytest.fixture
def file_isc_voc(file_ivonne: Path) -> Path:
    path = file_ivonne.parent / "jogging_10m_isc_voc.h5"
    if not path.exists():
        with ivonne.Reader(file_ivonne) as db:
            db.upsample_2_isc_voc(path, duration_s=5)
    return path


@pytest.fixture
def file_ivcurve(file_ivonne: Path) -> Path:
    path = file_ivonne.parent / "jogging_10m_ivcurve.h5"
    if not path.exists():
        with ivonne.Reader(file_ivonne) as db:
            db.convert_2_ivcurves(path, duration_s=5)
    return path


@pytest.fixture
def file_ivsample(file_ivonne: Path) -> Path:
    path = file_ivonne.parent / "jogging_10m_ivsample.h5"
    if not path.exists():
        with ivonne.Reader(file_ivonne) as db:
            tr_opt = mppt.OptimalTracker()
            db.convert_2_ivsamples(path, tracker=tr_opt, duration_s=5)
    return path
