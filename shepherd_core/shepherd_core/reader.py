"""Reader-Baseclass."""

from __future__ import annotations

import contextlib
import errno
import logging
import math
import os
from itertools import product
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any
from typing import ClassVar
from typing import Optional
from typing import Union

import h5py
import numpy as np
import yaml
from pydantic import validate_call
from tqdm import trange
from typing_extensions import Self

from .commons import samplerate_sps_default
from .data_models.base.calibration import CalibrationPair
from .data_models.base.calibration import CalibrationSeries
from .data_models.content.energy_environment import EnergyDType
from .decoder_waveform import Uart

if TYPE_CHECKING:
    from collections.abc import Generator
    from types import TracebackType


class Reader:
    """Sequentially Reads shepherd-data from HDF5 file.

    Args:
    ----
        file_path: Path of hdf5 file containing shepherd data with iv-samples, iv-curves or isc&voc
        verbose: more debug-info during usage, 'None' skips the setter

    """

    samples_per_buffer: int = 10_000

    mode_dtype_dict: ClassVar[dict] = {
        "harvester": [
            EnergyDType.ivsample,
            EnergyDType.ivcurve,
            EnergyDType.isc_voc,
        ],
        "emulator": [EnergyDType.ivsample],
    }

    @validate_call
    def __init__(
        self,
        file_path: Optional[Path],
        *,
        verbose: Optional[bool] = True,
    ) -> None:
        if not hasattr(self, "file_path"):
            self.file_path: Optional[Path] = None
            if isinstance(file_path, (Path, str)):
                self.file_path = Path(file_path).resolve()

        if not hasattr(self, "_logger"):
            self._logger: logging.Logger = logging.getLogger("SHPCore.Reader")
        if verbose is not None:
            self._logger.setLevel(logging.DEBUG if verbose else logging.INFO)

        if not hasattr(self, "samplerate_sps"):
            self.samplerate_sps: int = samplerate_sps_default
        self.sample_interval_ns: int = round(10**9 // self.samplerate_sps)
        self.sample_interval_s: float = 1 / self.samplerate_sps

        self.max_elements: int = 40 * self.samplerate_sps
        # ⤷ per iteration (40s full res, < 200 MB RAM use)

        # init stats
        self.runtime_s: float = 0
        self.buffers_n: int = 0
        self.file_size: int = 0
        self.data_rate: float = 0

        # open file (if not already done by writer)
        self._reader_opened: bool = False
        if not hasattr(self, "h5file"):
            if not isinstance(self.file_path, Path):
                raise TypeError("Provide a valid Path-Object to Reader!")
            if not (self.file_path.exists() and self.file_path.is_file()):
                raise FileNotFoundError(
                    errno.ENOENT, os.strerror(errno.ENOENT), self.file_path.name
                )

            try:
                self.h5file = h5py.File(self.file_path, "r")  # = readonly
                self._reader_opened = True
            except OSError as _xcp:
                msg = f"Unable to open HDF5-File '{self.file_path.name}'"
                raise TypeError(msg) from _xcp

            if self.is_valid():
                self._logger.debug("File is available now")
            else:
                self._logger.error(
                    "[FileValidation] File is faulty! "
                    "Will try to open but there might be dragons, for '%s'",
                    self.file_path.name,
                )

        if not isinstance(self.file_path, Path):
            raise TypeError("Provide a valid Path-Object to Base-Reader.file_path!")
        if not isinstance(self.h5file, h5py.File):
            raise TypeError("Type of opened file is not h5py.File, for %s", self.file_path.name)

        self.ds_time: h5py.Dataset = self.h5file["data"]["time"]
        self.ds_voltage: h5py.Dataset = self.h5file["data"]["voltage"]
        self.ds_current: h5py.Dataset = self.h5file["data"]["current"]

        # retrieve cal-data
        if not hasattr(self, "_cal"):
            cal_dict = CalibrationSeries().model_dump()
            for ds, param in product(["current", "voltage", "time"], ["gain", "offset"]):
                try:
                    cal_dict[ds][param] = self.h5file["data"][ds].attrs[param]
                except KeyError:  # noqa: PERF203
                    self._logger.debug("Cal-Param '%s' for dataset '%s' not found!", param, ds)
            self._cal = CalibrationSeries(**cal_dict)

        self._refresh_file_stats()

        if file_path is not None:
            # file opened by this reader
            self._logger.debug(
                "Reading data from '%s'\n"
                "\t- runtime %.1f s\n"
                "\t- mode = %s\n"
                "\t- window_size = %d\n"
                "\t- size = %.3f MiB\n"
                "\t- rate = %.0f KiB/s",
                self.file_path.name,
                self.runtime_s,
                self.get_mode(),
                self.get_window_samples(),
                self.file_size / 2**20,
                self.data_rate / 2**10,
            )

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        typ: Optional[type[BaseException]] = None,
        exc: Optional[BaseException] = None,
        tb: Optional[TracebackType] = None,
        extra_arg: int = 0,
    ) -> None:
        if self._reader_opened:
            self.h5file.close()

    def __repr__(self) -> str:
        return yaml.safe_dump(
            self.get_metadata(minimal=True), default_flow_style=False, sort_keys=False
        )

    def _refresh_file_stats(self) -> None:
        """Update internal states, helpful after resampling or other changes in data-group."""
        self.h5file.flush()
        sample_count = self.ds_time.shape[0]
        duration_raw = (
            (int(self.ds_time[sample_count - 1]) - int(self.ds_time[0])) if sample_count > 0 else 0
        )
        # above's typecasting prevents overflow in u64-format
        if (sample_count > 0) and (duration_raw > 0):
            # this assumes iso-chronous sampling
            duration_s = self._cal.time.raw_to_si(duration_raw)
            self.sample_interval_s = duration_s / sample_count
            self.sample_interval_ns = round(10**9 * self.sample_interval_s)
            self.samplerate_sps = max(round((sample_count - 1) / duration_s), 1)
        self.runtime_s = round(self.ds_voltage.shape[0] / self.samplerate_sps, 1)
        self.buffers_n = int(self.ds_voltage.shape[0] // self.samples_per_buffer)
        if isinstance(self.file_path, Path):
            self.file_size = self.file_path.stat().st_size
        else:
            self.file_size = 0
        self.data_rate = self.file_size / self.runtime_s if self.runtime_s > 0 else 0

    def read_buffers(
        self,
        start_n: int = 0,
        end_n: Optional[int] = None,
        n_samples_per_buffer: Optional[int] = None,
        *,
        is_raw: bool = False,
        omit_ts: bool = False,
    ) -> Generator[tuple, None, None]:
        """Read the specified range of buffers from the hdf5 file.

        Generator - can be configured on first call

        Args:
        ----
            :param start_n: (int) Index of first buffer to be read
            :param end_n: (int) Index of last buffer to be read
            :param n_samples_per_buffer: (int) allows changing
            :param is_raw: (bool) output original data, not transformed to SI-Units
            :param omit_ts: (bool) optimize reading if timestamp is never used
        Yields: Buffers between start and end (tuple with time, voltage, current)

        """
        if n_samples_per_buffer is None:
            n_samples_per_buffer = self.samples_per_buffer
        end_max = int(self.ds_voltage.shape[0] // n_samples_per_buffer)
        end_n = end_max if end_n is None else min(end_n, end_max)
        self._logger.debug("Reading blocks %d to %d from source-file", start_n, end_n)
        _raw = is_raw
        _wts = not omit_ts

        for i in range(start_n, end_n):
            idx_start = i * n_samples_per_buffer
            idx_end = idx_start + n_samples_per_buffer
            if _raw:
                yield (
                    self.ds_time[idx_start:idx_end] if _wts else None,
                    self.ds_voltage[idx_start:idx_end],
                    self.ds_current[idx_start:idx_end],
                )
            else:
                yield (
                    self._cal.time.raw_to_si(self.ds_time[idx_start:idx_end]) if _wts else None,
                    self._cal.voltage.raw_to_si(self.ds_voltage[idx_start:idx_end]),
                    self._cal.current.raw_to_si(self.ds_current[idx_start:idx_end]),
                )

    def get_calibration_data(self) -> CalibrationSeries:
        """Read calibration-data from hdf5 file.

        :return: Calibration data as CalibrationSeries object
        """
        return self._cal

    def get_window_samples(self) -> int:
        if "window_samples" in self.h5file["data"].attrs:
            return int(self.h5file["data"].attrs["window_samples"])
        return 0

    def get_mode(self) -> str:
        if "mode" in self.h5file.attrs:
            return self.h5file.attrs["mode"]
        return ""

    def get_config(self) -> dict:
        if "config" in self.h5file["data"].attrs:
            return yaml.safe_load(self.h5file["data"].attrs["config"])
        return {}

    def get_hostname(self) -> str:
        if "hostname" in self.h5file.attrs:
            return self.h5file.attrs["hostname"]
        return "unknown"

    def get_datatype(self) -> Optional[EnergyDType]:
        try:
            if "datatype" in self.h5file["data"].attrs:
                return EnergyDType[self.h5file["data"].attrs["datatype"]]
        except KeyError:
            return None
        except ValueError:
            return None
        else:
            return None

    def get_voltage_step(self) -> Optional[float]:
        """Informs about the voltage step (in volts) used during harvesting the ivcurve.

        Options for figuring out the real step:
        - look into config (if available)
        - analyze recorded data for most often used delta
        - calculate with 'steps_n * (1 + wait_cycles)' (done for calculating window_size)
        """
        voltage_step: Optional[float] = (
            self.get_config().get("virtual_harvester", {}).get("voltage_step_mV", None)
        )
        if voltage_step is None:
            dsv = self.ds_voltage[0:2000]
            diffs_np = np.unique(dsv[1:] - dsv[0:-1], return_counts=False)
            diffs_ls = [_e for _e in list(np.array(diffs_np)) if _e > 0]
            # static voltages have 0 steps, so
            if len(diffs_ls) == 0:
                return None  # or is 0 better? that may provoke div0
            voltage_step = min(diffs_ls)
        if voltage_step is not None:
            voltage_step = 1e-3 * voltage_step
        return voltage_step

    def get_hrv_config(self) -> dict:
        """Essential info for harvester.

        :return: config-dict directly for vHarvester to be used during emulation
        """
        return {
            "datatype": self.get_datatype(),
            "window_samples": self.get_window_samples(),
            "voltage_step_V": self.get_voltage_step(),
        }

    def is_valid(self) -> bool:
        """Check file for plausibility, validity / correctness.

        :return: state of validity
        """
        # hard criteria
        if "data" not in self.h5file:
            self._logger.error(
                "[FileValidation] root data-group not found in '%s'",
                self.file_path.name,
            )
            return False
        for attr in ["mode"]:
            if attr not in self.h5file.attrs:
                self._logger.error(
                    "[FileValidation] attribute '%s' not found in '%s'",
                    attr,
                    self.file_path.name,
                )
                return False
            if self.h5file.attrs["mode"] not in self.mode_dtype_dict:
                self._logger.error(
                    "[FileValidation] unsupported mode '%s' in '%s'",
                    attr,
                    self.file_path.name,
                )
                return False
        for attr in ["window_samples", "datatype"]:
            if attr not in self.h5file["data"].attrs:
                self._logger.error(
                    "[FileValidationError] attribute '%s' not found in data-group in '%s'",
                    attr,
                    self.file_path.name,
                )
                return False
        for dset in ["time", "current", "voltage"]:
            if dset not in self.h5file["data"]:
                self._logger.error(
                    "[FileValidation] dataset '%s' not found in '%s'",
                    dset,
                    self.file_path.name,
                )
                return False
            for attr in ["gain", "offset"]:
                if attr not in self.h5file["data"][dset].attrs:
                    self._logger.error(
                        "[FileValidation] attribute '%s' not found in dataset '%s' in '%s'",
                        attr,
                        dset,
                        self.file_path.name,
                    )
                    return False
        if self.get_datatype() not in self.mode_dtype_dict[self.get_mode()]:
            self._logger.error(
                "[FileValidation] unsupported type '%s' for mode '%s'  in '%s'",
                self.get_datatype(),
                self.get_mode(),
                self.file_path.name,
            )
            return False

        if self.get_datatype() == EnergyDType.ivcurve and self.get_window_samples() < 1:
            self._logger.error(
                "[FileValidation] window size / samples is < 1 "
                "-> invalid for ivcurve-datatype, in '%s'",
                self.file_path.name,
            )
            return False

        # soft-criteria:
        if self.get_datatype() != EnergyDType.ivcurve and self.get_window_samples() > 0:
            self._logger.warning(
                "[FileValidation] window size / samples is > 0 despite "
                "not using the ivcurve-datatype, in '%s'",
                self.file_path.name,
            )
        # same length of datasets:
        ds_volt_size = self.h5file["data"]["voltage"].shape[0]
        for dset in ["current", "time"]:
            ds_size = self.h5file["data"][dset].shape[0]
            if ds_volt_size != ds_size:
                self._logger.warning(
                    "[FileValidation] dataset '%s' has different size (=%d), "
                    "compared to time-ds (=%d), in '%s'",
                    dset,
                    ds_size,
                    ds_volt_size,
                    self.file_path.name,
                )
        # dataset-length should be multiple of buffersize
        remaining_size = ds_volt_size % self.samples_per_buffer
        if remaining_size != 0:
            self._logger.warning(
                "[FileValidation] datasets are not aligned with buffer-size in '%s'",
                self.file_path.name,
            )
        # check compression
        for dset in ["time", "current", "voltage"]:
            comp = self.h5file["data"][dset].compression
            opts = self.h5file["data"][dset].compression_opts
            if comp not in {None, "gzip", "lzf"}:
                self._logger.warning(
                    "[FileValidation] unsupported compression found "
                    "(%s != None, lzf, gzip) in '%s'",
                    comp,
                    self.file_path.name,
                )
            if (comp == "gzip") and (opts is not None) and (int(opts) > 1):
                self._logger.warning(
                    "[FileValidation] gzip compression is too high (%d > 1) for BBone in '%s'",
                    opts,
                    self.file_path.name,
                )
        # host-name
        if self.get_hostname() == "unknown":
            self._logger.warning(
                "[FileValidation] Hostname was not set in '%s'", self.file_path.name
            )
        # errors during execution
        _err = self.count_errors_in_log()
        if _err > 0:
            self._logger.warning(
                "[FileValidation] Sheep reported %d errors during execution -> check logs in '%s'",
                _err,
                self.file_path.name,
            )
        return True

    def __getitem__(self, key: str) -> Any:
        """Query attribute or (if none found) a handle for a group or dataset (if found).

        :param key: attribute, group, dataset
        :return: value of that key, or handle of object
        """
        if key in self.h5file.attrs:
            return self.h5file.attrs.__getitem__(key)
        if key in self.h5file:
            return self.h5file.__getitem__(key)
        raise KeyError

    def energy(self) -> float:
        """Determine the recorded energy of the trace.

        # multiprocessing: https://stackoverflow.com/a/71898911
        # -> failed with multiprocessing.pool and pathos.multiprocessing.ProcessPool.

        :return: sampled energy in Ws (watt-seconds)
        """
        iterations = math.ceil(self.ds_voltage.shape[0] / self.max_elements)
        job_iter = trange(
            0,
            self.ds_voltage.shape[0],
            self.max_elements,
            desc="energy",
            leave=False,
            disable=iterations < 8,
        )

        def _calc_energy(idx_start: int) -> float:
            idx_stop = min(idx_start + self.max_elements, self.ds_voltage.shape[0])
            vol_v = self._cal.voltage.raw_to_si(self.ds_voltage[idx_start:idx_stop])
            cur_a = self._cal.current.raw_to_si(self.ds_current[idx_start:idx_stop])
            return (vol_v[:] * cur_a[:]).sum() * self.sample_interval_s

        energy_ws = [_calc_energy(i) for i in job_iter]
        return float(sum(energy_ws))

    def _dset_statistics(
        self, dset: h5py.Dataset, cal: Optional[CalibrationPair] = None
    ) -> dict[str, float]:
        """Create basic stats for a provided dataset.

        :param dset: dataset to evaluate
        :param cal: calibration (if wanted)
        :return: dict with entries for mean, min, max, std
        """
        si_converted = True
        if not isinstance(cal, CalibrationPair):
            if "gain" in dset.attrs and "offset" in dset.attrs:
                cal = CalibrationPair(gain=dset.attrs["gain"], offset=dset.attrs["offset"])
            else:
                cal = CalibrationPair(gain=1)
                si_converted = False
        iterations = math.ceil(dset.shape[0] / self.max_elements)
        job_iter = trange(
            0,
            dset.shape[0],
            self.max_elements,
            desc=f"{dset.name}-stats",
            leave=False,
            disable=iterations < 8,
        )

        def _calc_statistics(data: np.ndarray) -> list:
            return [np.mean(data), np.min(data), np.max(data), np.std(data)]

        stats_list = [
            _calc_statistics(cal.raw_to_si(dset[i : i + self.max_elements])) for i in job_iter
        ]
        if len(stats_list) < 1:
            return {}
        stats_nd = np.stack(stats_list)
        stats: dict[str, float] = {
            # TODO: wrong calculation for ndim-datasets with n>1
            "mean": float(stats_nd[:, 0].mean()),
            "min": float(stats_nd[:, 1].min()),
            "max": float(stats_nd[:, 2].max()),
            "std": float(stats_nd[:, 3].mean()),  # TODO: sooo wrong :)
            "si_converted": si_converted,
        }
        return stats

    def _data_timediffs(self) -> list[float]:
        """Calculate list of unique time-deltas [s] between buffers.

        Optimized version that only looks at the start of each buffer.

        :return: list of (unique) time-deltas between buffers [s]
        """
        iterations = math.ceil(self.ds_time.shape[0] / self.max_elements)
        job_iter = trange(
            0,
            self.h5file["data"]["time"].shape[0],
            self.max_elements,
            desc="timediff",
            leave=False,
            disable=iterations < 8,
        )

        def calc_timediffs(idx_start: int) -> list:
            ds_time = self.ds_time[
                idx_start : (idx_start + self.max_elements) : self.samples_per_buffer
            ]
            diffs_np = np.unique(ds_time[1:] - ds_time[0:-1], return_counts=False)
            return list(np.array(diffs_np))

        diffs_ll = [calc_timediffs(i) for i in job_iter]
        diffs = {
            round(self._cal.time.raw_to_si(j) / self.samples_per_buffer, 6)
            for i in diffs_ll
            for j in i
        }
        return list(diffs)

    def check_timediffs(self) -> bool:
        """Validate equal time-deltas.

        Unexpected time-jumps hint at a corrupted file or faulty measurement.

        :return: True if OK
        """
        diffs = self._data_timediffs()
        if len(diffs) > 1:
            self._logger.warning(
                "Time-jumps detected -> expected equal steps, but got: %s s", diffs
            )
        return (len(diffs) <= 1) and diffs[0] == round(0.1 / self.samples_per_buffer, 6)

    def count_errors_in_log(self, group_name: str = "sheep", min_level: int = 40) -> int:
        if group_name not in self.h5file:
            return 0
        if "level" not in self.h5file[group_name]:
            return 0
        _lvl = self.h5file[group_name]["level"]
        if _lvl.shape[0] < 1:
            return 0
        _items = [1 for _x in _lvl[:] if _x >= min_level]
        return len(_items)

    def get_metadata(
        self,
        node: Union[h5py.Dataset, h5py.Group, None] = None,
        *,
        minimal: bool = False,
    ) -> dict[str, dict]:
        """Recursive FN to capture the structure of the file.

        :param node: starting node, leave free to go through whole file
        :param minimal: just provide a bare tree (much faster)
        :return: structure of that node with everything inside it
        """
        if node is None:
            self._refresh_file_stats()
            return self.get_metadata(self.h5file, minimal=minimal)

        metadata: dict[str, dict] = {}
        if isinstance(node, h5py.Dataset) and not minimal:
            metadata["_dataset_info"] = {
                "datatype": str(node.dtype),
                "shape": str(node.shape),
                "chunks": str(node.chunks),
                "compression": str(node.compression),
                "compression_opts": str(node.compression_opts),
            }
            if node.name == "/data/time":
                metadata["_dataset_info"]["time_diffs_s"] = self._data_timediffs()
                # TODO: already convert to str to calm the typechecker?
                #  or construct a pydantic-class
            elif "int" in str(node.dtype):
                metadata["_dataset_info"]["statistics"] = self._dset_statistics(node)
                # TODO: put this into metadata["_dataset_statistics"] ??
        for attr in node.attrs:
            attr_value = node.attrs[attr]
            if isinstance(attr_value, str):
                with contextlib.suppress(yaml.YAMLError):
                    attr_value = yaml.safe_load(attr_value)
            elif "int" in str(type(attr_value)):
                # TODO: why not isinstance? can it be list[int] other complex type?
                attr_value = int(attr_value)
            else:
                attr_value = float(attr_value)
            metadata[attr] = attr_value
        if isinstance(node, h5py.Group):
            if node.name == "/data" and not minimal:
                metadata["_group_info"] = {
                    "energy_Ws": self.energy(),
                    "runtime_s": round(self.runtime_s, 1),
                    "data_rate_KiB_s": round(self.data_rate / 2**10),
                    "file_size_MiB": round(self.file_size / 2**20, 3),
                    "valid": self.is_valid(),
                }
            for item in node:
                metadata[item] = self.get_metadata(node[item], minimal=minimal)

        return metadata

    def save_metadata(self, node: Union[h5py.Dataset, h5py.Group, None] = None) -> dict:
        """Get structure of file and dump content to yaml-file with same name as original.

        :param node: starting node, leave free to go through whole file
        :return: structure of that node with everything inside it
        """
        if isinstance(self.file_path, Path):
            yaml_path = Path(self.file_path).resolve().with_suffix(".yaml")
            if yaml_path.exists():
                self._logger.info("File already exists, will skip '%s'", yaml_path.name)
                return {}
            metadata = self.get_metadata(node)  # {"h5root": self.get_metadata(self.h5file)}
            with yaml_path.open("w", encoding="utf-8-sig") as yfd:
                yaml.safe_dump(metadata, yfd, default_flow_style=False, sort_keys=False)
        else:
            metadata = {}
        return metadata

    def get_gpio_pin_num(self, name: str) -> Optional[int]:
        # reverse lookup in a 2D-dict: key1 are pin_num, key2 are descriptor-names
        if "gpio" not in self.h5file:
            return None
        descriptions = yaml.safe_load(self.h5file["gpio"]["value"].attrs["description"])
        for desc_name, desc in descriptions.items():
            if name in desc["name"]:
                return int(desc_name)
        return None

    @staticmethod
    def get_filter_for_redundant_states(data: np.ndarray) -> np.ndarray:
        """Input is 1D state-vector, kep only first from identical & sequential states.

        Algo: create an offset-by-one vector and compare against original.
        """
        if len(data.shape) > 1:
            raise ValueError("Array must be 1D")
        data_1 = np.concatenate(([not data[0]], data[:-1]))
        return data != data_1

    def gpio_to_waveforms(self, name: Optional[str] = None) -> dict:
        waveforms: dict[str, np.ndarray] = {}
        if "gpio" not in self.h5file:
            return waveforms

        gpio_ts = self.h5file["gpio"]["time"]
        gpio_vs = self.h5file["gpio"]["value"]

        if name is None:
            descriptions = yaml.safe_load(self.h5file["gpio"]["value"].attrs["description"])
            pin_dict = {value["name"]: key for key, value in descriptions.items()}
        else:
            pin_dict = {name: self.get_gpio_pin_num(name)}

        for pin_name, pin_num in pin_dict.items():
            gpio_ps = (gpio_vs[:] & (0b1 << pin_num)) > 0
            gpio_f = self.get_filter_for_redundant_states(gpio_ps)
            waveforms[pin_name] = np.column_stack((gpio_ts[gpio_f], gpio_ps[gpio_f]))
            self._logger.debug(
                "GPIO '%s' has %d state-changes (includes initial state)",
                pin_name,
                sum(gpio_f),
            )
        return waveforms

    def waveform_to_csv(self, pin_name: str, pin_wf: np.ndarray, separator: str = ",") -> None:
        path_csv = self.file_path.with_suffix(f".waveform.{pin_name}.csv")
        if path_csv.exists():
            self._logger.info("File already exists, will skip '%s'", path_csv.name)
            return
        with path_csv.open("w") as csv:
            csv.write(f"timestamp [s],{pin_name}\n")
            for row in pin_wf:
                csv.write(f"{row[0] / 1e9}{separator}{int(row[1])}\n")

    def gpio_to_uart(self) -> Optional[np.ndarray]:
        wfs = self.gpio_to_waveforms("uart")
        if len(wfs) < 1:
            return None
        pin_name, pin_wf = wfs.popitem()

        write_to_file = False
        if write_to_file:
            self.waveform_to_csv(pin_name, pin_wf)

        gpio_wf = pin_wf.astype(float)
        gpio_wf[:, 0] = gpio_wf[:, 0] / 1e9

        try:
            return Uart(gpio_wf).get_lines()
        except TypeError:
            self._logger.error("TypeError: Extracting UART from GPIO failed - will skip file.")
            return None
        except ValueError:
            self._logger.error("ValueError: Extracting UART from GPIO failed - will skip file.")
            return None
