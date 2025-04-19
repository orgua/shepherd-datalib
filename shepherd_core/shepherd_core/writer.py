"""Writer that inherits from Reader-Baseclass."""

import logging
import math
import pathlib
from collections.abc import Mapping
from datetime import timedelta
from itertools import product
from pathlib import Path
from types import TracebackType
from typing import Any
from typing import Optional
from typing import Union

import h5py
import numpy as np
import yaml
from pydantic import validate_call
from typing_extensions import Self
from yaml import Node
from yaml import SafeDumper

from .commons import samplerate_sps_default
from .data_models.base.calibration import CalibrationEmulator as CalEmu
from .data_models.base.calibration import CalibrationHarvester as CalHrv
from .data_models.base.calibration import CalibrationSeries as CalSeries
from .data_models.content.energy_environment import EnergyDType
from .data_models.task import Compression
from .data_models.task.emulation import c_translate
from .reader import Reader


# copy of core/models/base/shepherd - needed also here
def path2str(
    dumper: SafeDumper, data: Union[pathlib.Path, pathlib.WindowsPath, pathlib.PosixPath]
) -> Node:
    """Add a yaml-representation for a specific datatype."""
    return dumper.represent_scalar("tag:yaml.org,2002:str", str(data.as_posix()))


def time2int(dumper: SafeDumper, data: timedelta) -> Node:
    """Add a yaml-representation for a specific datatype."""
    return dumper.represent_scalar("tag:yaml.org,2002:int", str(int(data.total_seconds())))


yaml.add_representer(pathlib.PosixPath, path2str, SafeDumper)
yaml.add_representer(pathlib.WindowsPath, path2str, SafeDumper)
yaml.add_representer(pathlib.Path, path2str, SafeDumper)
yaml.add_representer(timedelta, time2int, SafeDumper)


def unique_path(base_path: Union[str, Path], suffix: str) -> Path:
    """Find an unused filename in case it already exists.

    :param base_path: file-path to test
    :param suffix: file-suffix
    :return: new non-existing path
    """
    counter = 0
    while True:
        path = Path(base_path).with_suffix(f".{counter}{suffix}")
        if not path.exists():
            return path
        counter += 1


class Writer(Reader):
    """Stores data for Shepherd in HDF5 format.

    Choose lossless compression filter
     - lzf:  low to moderate compression, VERY fast, no options
             -> 20 % cpu overhead for half the filesize
     - gzip: good compression, moderate speed, select level from 1-9, default is 4
             -> lower levels seem fine
             -> _algo=number instead of "gzip" is read as compression level for gzip
     -> comparison / benchmarks https://www.h5py.org/lzf/

    Args:
    ----
        file_path: (Path) Name of the HDF5 file that data will be written to
        mode: (str) Indicates if this is data from harvester or emulator
        datatype: (str) choose type: ivsample (most common), ivcurve or isc_voc
        window_samples: (int) windows size for the datatype ivcurve
        cal_data: (CalibrationData) Data is written as raw ADC
            values. We need calibration data in order to convert to physical
            units later.
        modify_existing: (bool) explicitly enable modifying existing file
            otherwise a unique name will be found
        compression: (str) use either None, lzf or "1" (gzips compression level)
        verbose: (bool) provides more debug-info

    """

    comp_default: int = 1
    mode_default: str = "harvester"
    datatype_default: EnergyDType = EnergyDType.ivsample

    _chunk_shape: tuple = (Reader.samples_per_buffer,)

    @validate_call
    def __init__(
        self,
        file_path: Path,
        mode: Optional[str] = None,
        datatype: Union[str, EnergyDType, None] = None,
        window_samples: Optional[int] = None,
        cal_data: Union[CalSeries, CalEmu, CalHrv, None] = None,
        compression: Optional[Compression] = Compression.default,
        *,
        modify_existing: bool = False,
        force_overwrite: bool = False,
        verbose: Optional[bool] = True,
    ) -> None:
        self._modify = modify_existing
        if compression is not None:
            self._compression = c_translate[compression.value]
        else:
            self._compression = None

        if not hasattr(self, "_logger"):
            self._logger: logging.Logger = logging.getLogger("SHPCore.Writer")
        # -> logger gets configured in reader()

        if self._modify or force_overwrite or not file_path.exists():
            self.file_path: Path = file_path.resolve()
            self._logger.info("Storing data to   '%s'", self.file_path)
        elif file_path.exists() and not file_path.is_file():
            msg = f"Path is not a file ({file_path})"
            raise TypeError(msg)
        else:
            base_dir = file_path.resolve().parents[0]
            self.file_path = unique_path(base_dir / file_path.stem, file_path.suffix)
            self._logger.warning(
                "File '%s' already exists -> storing under '%s' instead",
                file_path,
                self.file_path.name,
            )

        # open file
        if self._modify:
            self.h5file = h5py.File(self.file_path, "r+")  # = rw
        else:
            if not self.file_path.parent.exists():
                self.file_path.parent.mkdir(parents=True)
            self.h5file = h5py.File(self.file_path, "w")
            # ⤷ write, truncate if exist
            self._create_skeleton()

        # Handle Mode
        if isinstance(mode, str) and mode not in self.mode_dtype_dict:
            msg = f"Can't handle mode '{mode}' (choose one of {self.mode_dtype_dict})"
            raise ValueError(msg)

        if mode is not None:
            self.h5file.attrs["mode"] = mode
        if "mode" not in self.h5file.attrs:
            self.h5file.attrs["mode"] = self.mode_default

        _dtypes = self.mode_dtype_dict[self.get_mode()]

        # Handle Datatype
        if isinstance(datatype, str):
            datatype = EnergyDType[datatype]
        if isinstance(datatype, EnergyDType) and datatype not in _dtypes:
            msg = f"Can't handle value '{datatype}' of datatype (choose one of {_dtypes})"
            raise ValueError(msg)

        if isinstance(datatype, EnergyDType):
            self.h5file["data"].attrs["datatype"] = datatype.name
        if "datatype" not in self.h5file["data"].attrs:
            self.h5file["data"].attrs["datatype"] = self.datatype_default.name
        if self.get_datatype() not in _dtypes:
            msg = (
                f"Can't handle value '{self.get_datatype()}' of datatype (choose one of {_dtypes})"
            )
            raise ValueError(msg)

        # Handle Window_samples
        if window_samples is not None:
            self.h5file["data"].attrs["window_samples"] = window_samples
        if "window_samples" not in self.h5file["data"].attrs:
            self.h5file["data"].attrs["window_samples"] = 0

        if datatype == EnergyDType.ivcurve and self.get_window_samples() < 1:
            raise ValueError("Window Size argument needed for ivcurve-Datatype")

        # Handle Cal
        if isinstance(cal_data, (CalEmu, CalHrv)):
            cal_data = CalSeries.from_cal(cal_data)

        if isinstance(cal_data, CalSeries):
            for ds, param in product(["current", "voltage", "time"], ["gain", "offset"]):
                self.h5file["data"][ds].attrs[param] = cal_data[ds][param]
        else:
            # check if there are unset cal-values and set them to default
            cal_data = CalSeries()
            for ds, param in product(["current", "voltage", "time"], ["gain", "offset"]):
                if param not in self.h5file["data"][ds].attrs:
                    self.h5file["data"][ds].attrs[param] = cal_data[ds][param]

        # show key parameters for h5-performance
        settings = list(self.h5file.id.get_access_plist().get_cache())
        self._logger.debug("H5Py Cache_setting=%s (_mdc, _nslots, _nbytes, _w0)", settings)

        super().__init__(file_path=None, verbose=verbose)

    def __enter__(self) -> Self:
        super().__enter__()
        return self

    def __exit__(
        self,
        typ: Optional[type[BaseException]] = None,
        exc: Optional[BaseException] = None,
        tb: Optional[TracebackType] = None,
        extra_arg: int = 0,
    ) -> None:
        self._align()
        self._refresh_file_stats()
        self._logger.info(
            "closing hdf5 file, %.1f s iv-data, size = %.3f MiB, rate = %.0f KiB/s",
            self.runtime_s,
            self.file_size / 2**20,
            self.data_rate / 2**10,
        )
        self.is_valid()
        self.h5file.close()

    def _create_skeleton(self) -> None:
        """Initialize the structure of the HDF5 file.

        HDF5 is hierarchically structured and before writing data, we have to
        set up this structure, i.e. creating the right groups with corresponding
        data types. We will store 3 types of data in a database: The
        actual IV samples recorded either from the harvester (during recording)
        or the target (during emulation). Any log messages, that can be used to
        store relevant events or tag some parts of the recorded data.

        """
        # Store voltage and current samples in the data group,
        # both are stored as 4 Byte unsigned int
        grp_data = self.h5file.create_group("data")
        # the size of window_samples-attribute in harvest-data indicates ivcurves as input
        # -> emulator uses virtual-harvester, field will be adjusted by .embed_config()
        grp_data.attrs["window_samples"] = 0

        grp_data.create_dataset(
            "time",
            (0,),
            dtype="u8",
            maxshape=(None,),
            chunks=self._chunk_shape,
            compression=self._compression,
        )
        grp_data["time"].attrs["unit"] = "s"
        grp_data["time"].attrs["description"] = "system time [s] = value * gain + (offset)"

        grp_data.create_dataset(
            "current",
            (0,),
            dtype="u4",
            maxshape=(None,),
            chunks=self._chunk_shape,
            compression=self._compression,
        )
        grp_data["current"].attrs["unit"] = "A"
        grp_data["current"].attrs["description"] = "current [A] = value * gain + offset"

        grp_data.create_dataset(
            "voltage",
            (0,),
            dtype="u4",
            maxshape=(None,),
            chunks=self._chunk_shape,
            compression=self._compression,
        )
        grp_data["voltage"].attrs["unit"] = "V"
        grp_data["voltage"].attrs["description"] = "voltage [V] = value * gain + offset"

    def append_iv_data_raw(
        self,
        timestamp: Union[np.ndarray, float, int],  # noqa: PYI041
        voltage: np.ndarray,
        current: np.ndarray,
    ) -> None:
        """Write raw data to database.

        Args:
        ----
            timestamp: just start of buffer or whole ndarray
            voltage: ndarray as raw unsigned integers
            current: ndarray as raw unsigned integers

        """
        len_new = min(voltage.size, current.size)

        if isinstance(timestamp, float):
            timestamp = int(timestamp)
        if isinstance(timestamp, int):
            time_series_ns = self.sample_interval_ns * np.arange(len_new).astype("u8")
            timestamp = timestamp + time_series_ns
        if isinstance(timestamp, np.ndarray):
            len_new = min(len_new, timestamp.size)
        else:
            raise TypeError("timestamp-data was not usable")

        len_old = self.ds_voltage.shape[0]

        # resize dataset
        self.ds_time.resize((len_old + len_new,))
        self.ds_voltage.resize((len_old + len_new,))
        self.ds_current.resize((len_old + len_new,))

        # append new data
        self.ds_time[len_old : len_old + len_new] = timestamp[:len_new]
        self.ds_voltage[len_old : len_old + len_new] = voltage[:len_new]
        self.ds_current[len_old : len_old + len_new] = current[:len_new]

    def append_iv_data_si(
        self,
        timestamp: Union[np.ndarray, float],
        voltage: np.ndarray,
        current: np.ndarray,
    ) -> None:
        """Write data (provided in SI / physical unit) to file.

        This will convert it to raw-data first.

           SI-value [SI-Unit] = raw-value * gain + offset,

        Args:
        ----
            timestamp: python timestamp (time.time()) in seconds (si-unit)
                       -> provide start of buffer or whole ndarray
            voltage: ndarray in physical-unit V
            current: ndarray in physical-unit A

        """
        # TODO: make timestamp optional to add it raw, OR unify append with granular raw-switch
        timestamp = self._cal.time.si_to_raw(timestamp)
        voltage = self._cal.voltage.si_to_raw(voltage)
        current = self._cal.current.si_to_raw(current)
        self.append_iv_data_raw(timestamp, voltage, current)

    def _align(self) -> None:
        """Align datasets with buffer-size of shepherd."""
        self._refresh_file_stats()
        n_buff = self.ds_voltage.size / self.samples_per_buffer
        size_new = int(math.floor(n_buff) * self.samples_per_buffer)
        if size_new < self.ds_voltage.size:
            if self.samplerate_sps != samplerate_sps_default:
                self._logger.debug("skipped alignment due to altered samplerate")
                return
            self._logger.info(
                "aligning with buffer-size, discarding last %d entries",
                self.ds_voltage.size - size_new,
            )
            self.ds_time.resize((size_new,))
            self.ds_voltage.resize((size_new,))
            self.ds_current.resize((size_new,))

    def __setitem__(self, key: str, item: Any) -> None:
        """Conveniently store relevant key-value data (attribute) in H5-structure."""
        self.h5file.attrs.__setitem__(key, item)

    def store_config(self, data: Mapping) -> None:
        """Get a better self-describing Output-File.

        TODO: use data-model?
        :param data: from virtual harvester or converter / source.
        """
        self.h5file.attrs["config"] = yaml.safe_dump(
            data, default_flow_style=False, sort_keys=False
        )

    def store_hostname(self, name: str) -> None:
        """Option to distinguish the host, target or data-source -> perfect for plotting later.

        :param name: something unique, or "artificial" in case of generated content
        """
        self.h5file.attrs["hostname"] = name
