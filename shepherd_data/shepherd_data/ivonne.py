"""file-reader with various converters to generate valid shepherd-data for emulation.

IVonne uses the Shockley Diode Equation to estimate a model
I_D = I_S * ( e ^ ( U_D / n*U_T ) - 1 )
coeff_a = I_D = I_SC
coeff_b = I_S
coeff_c = 1 / n*U_T = q / n*k*T (constant)

literature: https://en.wikipedia.org/wiki/Shockley_diode_equation
"""

import errno
import logging
import math
import os
import pickle
from pathlib import Path
from types import TracebackType
from typing import Optional

import numpy as np
import pandas as pd
from tqdm import trange
from typing_extensions import Self

from . import Writer
from .mppt import MPPTracker
from .mppt import OptimalTracker
from .mppt import iv_model


def get_voc(coeffs: pd.DataFrame):  # noqa: ANN201
    """Open-circuit voltage of IV curve with given coefficients."""
    return np.log(coeffs["a"] / coeffs["b"] + 1) / coeffs["c"]


def get_isc(coeffs: pd.DataFrame):  # noqa: ANN201
    """Short-circuit current of IV curve with given coefficients."""
    return coeffs["a"]


class Reader:
    """Container for converters that bridge the gap to shepherds data-files."""

    _logger: logging.Logger = logging.getLogger("SHPData.IVonne.Reader")

    def __init__(
        self,
        file_path: Path,
        samplerate_sps: Optional[int] = None,
        *,
        verbose: bool = True,
    ) -> None:
        self._logger.setLevel(logging.INFO if verbose else logging.WARNING)

        self.file_path = Path(file_path).resolve()
        self.samplerate_sps: int = 50
        if samplerate_sps is not None:
            self.samplerate_sps = samplerate_sps

        self.sample_interval_ns: int = int(10**9 // self.samplerate_sps)
        self.sample_interval_s: float = 1 / self.samplerate_sps

        self.runtime_s: float = 0
        self.file_size: int = 0
        self.data_rate: float = 0

        self._df: Optional[pd.DataFrame] = None

    def __enter__(self) -> Self:
        if not self.file_path.exists():
            raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), self.file_path.name)
        with self.file_path.open("rb") as ifr:
            self._df = pickle.load(ifr)  # noqa: S301
        self._refresh_file_stats()
        self._logger.debug(
            "Reading data from '%s'\n"
            "\t- runtime = %d s\n"
            "\t- size = %.3f KiB\n"
            "\t- rate = %.3f KiB/s",
            self.file_path.name,
            self.runtime_s,
            self.file_size / 2**10,
            self.data_rate / 2**10,
        )
        return self

    def __exit__(
        self,
        typ: Optional[type[BaseException]] = None,
        exc: Optional[BaseException] = None,
        tb: Optional[TracebackType] = None,
        extra_arg: int = 0,
    ) -> None:
        pass

    def _refresh_file_stats(self) -> None:
        if self._df is None:
            raise RuntimeError("IVonne Context was not entered - file not open!")
        self.runtime_s = round(self._df.shape[0] / self.samplerate_sps, 3)
        self.file_size = self.file_path.stat().st_size
        self.data_rate = self.file_size / self.runtime_s if self.runtime_s > 0 else 0

    def convert_2_ivcurves(
        self,
        shp_output: Path,
        v_max: float = 5.0,
        pts_per_curve: int = 1000,
        duration_s: Optional[float] = None,
    ) -> None:
        """Transform recorded parameters to shepherd hdf database with IV curves.

        Shepherd works with IV 'surfaces', which is a stream of IV curves.

        :param shp_output: Path where the resulting hdf file shall be stored
        :param v_max: Maximum voltage supported by shepherd
        :param pts_per_curve: Number of sampling points of the prototype curve
        :param duration_s: time to stop in seconds, counted from beginning
        """
        if self._df is None:
            raise RuntimeError("IVonne Context was not entered - file not open!")
        if isinstance(duration_s, (float, int)) and self.runtime_s > duration_s:
            self._logger.info("  -> gets trimmed to %f s", duration_s)
            df_elements_n = min(self._df.shape[0], int(duration_s * self.samplerate_sps))
        else:
            df_elements_n = self._df.shape[0]

        if shp_output.exists():
            self._logger.info("File already exists, will skip '%s'", shp_output.name)
            return

        v_proto = np.linspace(0, v_max, pts_per_curve)

        with Writer(shp_output, datatype="ivcurve", window_samples=pts_per_curve) as sfw:
            sfw.store_hostname("IVonne")
            curve_interval_us = round(sfw.sample_interval_ns * pts_per_curve / 1000)
            up_factor = self.sample_interval_ns // sfw.sample_interval_ns
            max_elements = math.ceil(sfw.max_elements // up_factor)
            job_iter = trange(0, df_elements_n, max_elements, desc="generate ivcurves", leave=False)

            for idx in job_iter:
                idx_top = min(idx + max_elements, df_elements_n)
                df_slice = self._df.iloc[idx : idx_top + 1].copy()
                df_slice["timestamp"] = pd.to_timedelta(df_slice["time"], unit="s")
                df_slice = df_slice.set_index("timestamp")
                # warning: .interpolate does crash in debug-mode with typeError
                df_slice = (
                    df_slice.resample(f"{curve_interval_us}us")
                    .interpolate(method="cubic")
                    .iloc[:-1]
                )

                for _, coeffs in df_slice.iterrows():
                    i_proto = iv_model(v_proto, coeffs)

                    sfw.append_iv_data_si(coeffs["time"], v_proto, i_proto)
                # TODO: this could be a lot faster:
                #   - use lambdas to generate i_proto
                #   - convert i_proto with lambdas to raw-values
                #   - convert v_proto to raw
                #   - replace append_ fn with custom code here, by:
                #   - final size of h5-arrays is already known, this speeds up the code!
                #   - time can be generated and set as a whole
                #   - v_proto is repetitive, can also be set as a whole

    def convert_2_ivsamples(
        self,
        shp_output: Path,
        v_max: float = 5.0,
        duration_s: Optional[float] = None,
        tracker: Optional[MPPTracker] = None,
    ) -> None:
        """Transform shepherd IV curves to shepherd IV samples / traces.

        For the 'buck' and 'buck-boost' modes, shepherd takes voltage and current traces.
        These can be recorded with shepherd or generated from existing IV curves by, for
        example, maximum power point tracking. This function takes a shepherd IV curve
        file and applies the specified MPPT algorithm to extract the corresponding
        voltage and current traces.

        Todo:
        ----
            - allow to use harvester-model in shepherd-code
            - generalize and put it into main code

        :param shp_output: Path where the resulting hdf file shall be stored
        :param v_max: Maximum voltage supported by shepherd
        :param duration_s: time to stop in seconds, counted from beginning
        :param tracker: VOC or OPT

        """
        if self._df is None:
            raise RuntimeError("IVonne Context was not entered - file not open!")
        if isinstance(duration_s, (float, int)) and self.runtime_s > duration_s:
            self._logger.info("  -> gets trimmed to %f s", duration_s)
            df_elements_n = min(self._df.shape[0], int(duration_s * self.samplerate_sps))
        else:
            df_elements_n = self._df.shape[0]

        if shp_output.exists():
            self._logger.info("File already exists, will skip '%s'", shp_output.name)
            return

        if tracker is None:
            tracker = OptimalTracker(
                v_max,
            )

        with Writer(shp_output, datatype="ivsample") as sfw:
            sfw.store_hostname("IVonne")
            interval_us = round(sfw.sample_interval_ns / 1000)
            up_factor = self.sample_interval_ns // sfw.sample_interval_ns
            max_elements = math.ceil(sfw.max_elements // up_factor)
            job_iter = trange(
                0, df_elements_n, max_elements, desc="generate ivsamples", leave=False
            )

            for idx in job_iter:
                # select (max_elements + 1) elements, so upsampling is without gaps
                # -> drop a sample at the end
                idx_top = min(idx + max_elements, df_elements_n)
                df_slice = self._df.iloc[idx : idx_top + 1].copy()
                df_slice.loc[:, "voc"] = get_voc(df_slice)
                df_slice.loc[df_slice["voc"] >= v_max, "voc"] = v_max
                df_slice = tracker.process(df_slice)
                df_slice["timestamp"] = pd.to_timedelta(df_slice["time"], unit="s")
                df_slice = df_slice[["time", "v", "i", "timestamp"]].set_index("timestamp")
                # warning: .interpolate does crash in debug-mode with typeError
                df_slice = (
                    df_slice.resample(f"{interval_us}us").interpolate(method="cubic").iloc[:-1]
                )
                sfw.append_iv_data_si(
                    df_slice["time"].to_numpy(),
                    df_slice["v"].to_numpy(),
                    df_slice["i"].to_numpy(),
                )

    def upsample_2_isc_voc(
        self,
        shp_output: Path,
        v_max: float = 5.0,
        duration_s: Optional[float] = None,
    ) -> None:
        """Transform ivonne-parameters to up-sampled versions for shepherd.

        :param shp_output: Path where the resulting hdf file shall be stored
        :param v_max: Maximum voltage supported by shepherd
        :param duration_s: time to stop in seconds, counted from beginning
        """
        if self._df is None:
            raise RuntimeError("IVonne Context was not entered - file not open!")
        if isinstance(duration_s, (float, int)) and self.runtime_s > duration_s:
            self._logger.info("  -> gets trimmed to %f s", duration_s)
            df_elements_n = min(self._df.shape[0], int(duration_s * self.samplerate_sps))
        else:
            df_elements_n = self._df.shape[0]

        if shp_output.exists():
            self._logger.info("File already exists, will skip '%s'", shp_output.name)
            return

        with Writer(shp_output, datatype="isc_voc") as sfw:
            sfw.store_hostname("IVonne")
            interval_us = round(sfw.sample_interval_ns / 1000)
            up_factor = self.sample_interval_ns // sfw.sample_interval_ns
            max_elements = math.ceil(sfw.max_elements // up_factor)
            job_iter = trange(0, df_elements_n, max_elements, desc="generate upsample", leave=False)

            for idx in job_iter:
                # select (max_elements + 1) elements, so upsampling is without gaps
                # -> drop a sample at the end
                idx_top = min(idx + max_elements, df_elements_n)
                df_slice = self._df.iloc[idx : idx_top + 1].copy()
                df_slice.loc[:, "voc"] = get_voc(df_slice)
                df_slice.loc[df_slice["voc"] >= v_max, "voc"] = v_max
                df_slice.loc[:, "isc"] = get_isc(df_slice)
                df_slice["timestamp"] = pd.to_timedelta(df_slice["time"], unit="s")
                df_slice = df_slice[["time", "voc", "isc", "timestamp"]].set_index("timestamp")
                # warning: .interpolate does crash in debug-mode with typeError
                df_slice = (
                    df_slice.resample(f"{interval_us}us").interpolate(method="cubic").iloc[:-1]
                )
                sfw.append_iv_data_si(
                    df_slice["time"].to_numpy(),
                    df_slice["voc"].to_numpy(),
                    df_slice["isc"].to_numpy(),
                )
