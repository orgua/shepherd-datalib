"""Command definitions for CLI."""

import logging
import sys
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from typing import Optional

import click
import pydantic

from shepherd_core import get_verbose_level
from shepherd_core import local_tz
from shepherd_core.logger import set_log_verbose_level

from . import __version__
from .reader import Reader

logger = logging.getLogger("SHPData.cli")


def path_to_flist(data_path: Path, *, recurse: bool = False) -> list[Path]:
    """Every path gets transformed to a list of paths.

    Transformations:
    - if directory: list of files inside
    - if existing file: list with 1 element
    - or else: empty list
    """
    data_path = Path(data_path).resolve()
    h5files: list = []
    if data_path.is_file() and data_path.suffix.lower() == ".h5":
        h5files.append(data_path)
    elif data_path.is_dir():
        files = data_path.glob(
            "**/*.h5" if recurse else "*.h5"
        )  # for py>=3.12: case_sensitive=False
        h5files = [file for file in files if file.is_file()]
    return h5files


@click.group(context_settings={"help_option_names": ["-h", "--help"], "obj": {}})
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Switch from info- to debug-level",
)
@click.pass_context  # TODO: is the ctx-type correct?
def cli(ctx: click.Context, *, verbose: bool) -> None:
    """Shepherd: Synchronized Energy Harvesting Emulator and Recorder."""
    set_log_verbose_level(logger, 3 if verbose else 2)
    if not ctx.invoked_subcommand:
        click.echo("Please specify a valid command")


@cli.command(short_help="Print version-info (combine with -v for more)")
def version() -> None:
    """Print version-info (combine with -v for more)."""
    logger.info("Shepherd-Data v%s", __version__)
    logger.debug("Python v%s", sys.version)
    logger.debug("Click v%s", click.__version__)
    logger.debug("Pydantic v%s", pydantic.__version__)


@cli.command(short_help="Validates a file or directory containing shepherd-recordings")
@click.argument("in_data", type=click.Path(exists=True, resolve_path=True))
@click.option(
    "--recurse",
    "-a",
    is_flag=True,
    help="Also consider files in sub-folders",
)
def validate(in_data: Path, *, recurse: bool = False) -> None:
    """Validate a file or directory containing shepherd-recordings."""
    files = path_to_flist(in_data, recurse=recurse)
    verbose_level = get_verbose_level()  # TODO: should be stored and passed in ctx
    valid_dir = True
    for file in files:
        logger.info("Validating '%s' ...", file.name)
        valid_file = True
        try:
            with Reader(file, verbose=verbose_level > 2) as shpr:
                valid_file &= shpr.is_valid()
                valid_file &= shpr.check_timediffs()
                valid_dir &= valid_file
                if not valid_file:
                    logger.error(" -> File '%s' was NOT valid", file.name)
        except TypeError:
            logger.exception("ERROR: Will skip file. It caused an exception.")
    sys.exit(int(not valid_dir))


@cli.command(short_help="Extracts recorded IVSamples and stores it to csv")
@click.argument("in_data", type=click.Path(exists=True, resolve_path=True))
@click.option(
    "--start",
    "-s",
    default=None,
    type=click.FLOAT,
    help="Start-point in seconds, will be 0 if omitted",
)
@click.option(
    "--end",
    "-e",
    default=None,
    type=click.FLOAT,
    help="End-point in seconds, will be max if omitted",
)
@click.option(
    "--ds-factor",
    "-f",
    default=1000,
    type=click.FLOAT,
    help="Downsample-Factor, if one specific value is wanted",
)
@click.option(
    "--separator",
    default=";",
    type=click.STRING,
    help="Set an individual csv-separator",
)
@click.option(
    "--raw",
    "-r",
    is_flag=True,
    help="Don't convert data to si-units",
)
@click.option(
    "--recurse",
    "-a",
    is_flag=True,
    help="Also consider files in sub-folders",
)
def extract(
    in_data: Path,
    start: Optional[float],
    end: Optional[float],
    ds_factor: float,
    separator: str,
    *,
    raw: bool = False,
    recurse: bool = False,
) -> None:
    """Extract recorded IVSamples and store them to csv."""
    files = path_to_flist(in_data, recurse=recurse)
    verbose_level = get_verbose_level()
    if not isinstance(ds_factor, (float, int)) or ds_factor < 1:
        ds_factor = 1000
        logger.info("DS-Factor was invalid was reset to 1'000")
    for file in files:
        logger.info("Extracting IV-Samples from '%s' ...", file.name)
        try:
            with Reader(file, verbose=verbose_level > 2) as shpr:
                out_file = shpr.cut_and_downsample_to_file(start, end, ds_factor=ds_factor)
                with Reader(out_file, verbose=verbose_level > 2) as shpd:
                    shpd.save_csv(shpd["data"], separator, raw=raw)
        except (TypeError, ValueError):
            logger.exception("ERROR: Will skip file. It caused an exception.")


@cli.command(
    short_help="Extracts metadata and logs from file or directory containing shepherd-recordings"
)
@click.argument("in_data", type=click.Path(exists=True, resolve_path=True))
@click.option(
    "--separator",
    "-s",
    default=";",
    type=click.STRING,
    help="Set an individual csv-separator",
)
@click.option(
    "--recurse",
    "-a",
    is_flag=True,
    help="Also consider files in sub-folders",
)
def extract_meta(in_data: Path, separator: str, *, recurse: bool = False) -> None:
    """Extract metadata and logs from file or directory containing shepherd-recordings."""
    files = path_to_flist(in_data, recurse=recurse)
    verbose_level = get_verbose_level()
    for file in files:
        logger.info("Extracting metadata & logs from '%s' ...", file.name)
        # TODO: add default exports (user-centric) and allow specifying --all or specific ones
        # TODO: could also be combined with other extractors (just have one)
        try:
            with Reader(file, verbose=verbose_level > 2) as shpr:
                shpr.save_metadata()
                csvs_depr = ["sysutil", "timesync"]
                csvs = ["ptp", "sys_util", "pru_util"]
                for element in csvs + csvs_depr:
                    if element in shpr.h5file:
                        shpr.save_csv(shpr[element], separator)
                logs_depr = ["shepherd-log", "dmesg", "exceptions"]
                logs = ["sheep", "kernel", "phc2sys", "uart"]
                for element in logs + logs_depr:
                    if element in shpr.h5file:
                        shpr.save_log(shpr[element])
                        # TODO: allow omitting timestamp,
                        #       also test if segmented uart is correctly written
                        shpr.warn_logs(element, show=True)
        except TypeError:
            logger.exception("ERROR: Will skip file. It caused an exception.")


@cli.command(
    short_help="Extracts uart from gpio-trace in file or directory containing shepherd-recordings"
)
@click.argument("in_data", type=click.Path(exists=True, resolve_path=True))
@click.option(
    "--recurse",
    "-a",
    is_flag=True,
    help="Also consider files in sub-folders",
)
def extract_uart(in_data: Path, *, recurse: bool = False) -> None:
    """Extract UART from GPIO-trace in file or directory containing shepherd-recordings."""
    files = path_to_flist(in_data, recurse=recurse)
    verbose_level = get_verbose_level()
    for file in files:
        logger.info("Extracting uart from gpio-trace from from '%s' ...", file.name)
        try:
            with Reader(file, verbose=verbose_level > 2) as shpr:
                # TODO: move into separate fn OR add to h5-file and use .save_log(), ALSO TEST
                lines = shpr.gpio_to_uart()
                if lines is None:
                    continue
                # TODO: could also add parameter to get symbols instead of lines
                log_path = Path(file).with_suffix(".uart_from_wf.log")
                if log_path.exists():
                    logger.info("File already exists, will skip '%s'", log_path.name)
                    continue

                with log_path.open("w") as log_file:
                    for line in lines:
                        with suppress(TypeError):
                            timestamp = datetime.fromtimestamp(float(line[0]), tz=local_tz())
                            log_file.write(timestamp.strftime("%Y-%m-%d %H:%M:%S.%f") + ":")
                            # TODO: allow to skip Timestamp and export raw text
                            log_file.write(f"\t{str.encode(line[1])}")
                            # TODO: does this produce "\tb'abc'"?
                            log_file.write("\n")
        except TypeError:
            logger.exception("ERROR: Will skip file. It caused an exception.")


@cli.command(short_help="Extracts gpio-trace from file or directory containing shepherd-recordings")
@click.argument("in_data", type=click.Path(exists=True, resolve_path=True))
@click.option(
    "--separator",
    "-s",
    default=";",
    type=click.STRING,
    help="Set an individual csv-separator",
)  # TODO: also configure decimal point
@click.option(
    "--recurse",
    "-a",
    is_flag=True,
    help="Also consider files in sub-folders",
)
def extract_gpio(in_data: Path, separator: str, *, recurse: bool = False) -> None:
    """Extract UART from gpio-trace in file or directory containing shepherd-recordings."""
    files = path_to_flist(in_data, recurse=recurse)
    verbose_level = get_verbose_level()
    for file in files:
        logger.info("Extracting gpio-trace from from '%s' ...", file.name)
        try:
            with Reader(file, verbose=verbose_level > 2) as shpr:
                wfs = shpr.gpio_to_waveforms()
                for name, wf in wfs.items():
                    shpr.waveform_to_csv(name, wf, separator)
        except TypeError:
            logger.exception("ERROR: Will skip file. It caused an exception.")


@cli.command(
    short_help="Creates an array of down-sampled files from "
    "file or directory containing shepherd-recordings"
)
@click.argument("in_data", type=click.Path(exists=True, resolve_path=True))
@click.option(
    "--ds-factor",
    "-f",
    default=None,
    type=click.FLOAT,
    help="Downsample-Factor, if one specific value is wanted",
)
@click.option(
    "--sample-rate",
    "-r",
    type=click.INT,
    help="Alternative Input to determine a downsample-factor (Choose One)",
)
@click.option(
    "--start",
    "-s",
    default=None,
    type=click.FLOAT,
    help="Start-point in seconds, will be 0 if omitted",
)
@click.option(
    "--end",
    "-e",
    default=None,
    type=click.FLOAT,
    help="End-point in seconds, will be max if omitted",
)
@click.option(
    "--recurse",
    "-a",
    is_flag=True,
    help="Also consider files in sub-folders",
)
def downsample(
    in_data: Path,
    ds_factor: Optional[float],
    sample_rate: Optional[int],
    start: Optional[float],
    end: Optional[float],
    *,
    recurse: bool = False,
) -> None:
    """Create an array of down-sampled files from file or dir containing shepherd-recordings."""
    files = path_to_flist(in_data, recurse=recurse)
    verbose_level = get_verbose_level()
    for file in files:
        try:
            with Reader(file, verbose=verbose_level > 2) as shpr:
                if ds_factor is None and sample_rate is not None and sample_rate >= 1:
                    ds_factor = shpr.samplerate_sps / sample_rate

                if isinstance(ds_factor, (float, int)) and ds_factor >= 1:
                    ds_list = [ds_factor]
                else:
                    ds_list = [5, 25, 100, 500, 2_500, 10_000, 50_000, 250_000, 1_000_000]

                for _factor in ds_list:
                    path_file = shpr.cut_and_downsample_to_file(start, end, _factor)
                    logger.info("Created %s", path_file.name)
        except (TypeError, ValueError):  # noqa: PERF203
            logger.exception("ERROR: Will skip file. It caused an exception.")


@cli.command(short_help="Plots IV-trace from file or directory containing shepherd-recordings")
@click.argument("in_data", type=click.Path(exists=True, resolve_path=True))
@click.option(
    "--start",
    "-s",
    default=None,
    type=click.FLOAT,
    help="Start-point in seconds, will be 0 if omitted",
)
@click.option(
    "--end",
    "-e",
    default=None,
    type=click.FLOAT,
    help="End-point in seconds, will be max if omitted",
)
@click.option(
    "--width",
    "-w",
    default=20,
    type=click.INT,
    help="Width-Dimension of resulting plot",
)
@click.option(
    "--height",
    "-h",
    default=10,
    type=click.INT,
    help="Height-Dimension of resulting plot",
)
@click.option(
    "--multiplot",
    "-m",
    is_flag=True,
    help="Plot all files (in directory) into one Multiplot",
)
@click.option(
    "--only-power",
    "-p",
    is_flag=True,
    help="Plot only power instead of voltage, current & power",
)
@click.option(
    "--recurse",
    "-a",
    is_flag=True,
    help="Also consider files in sub-folders",
)
def plot(
    in_data: Path,
    start: Optional[float],
    end: Optional[float],
    width: int,
    height: int,
    *,
    multiplot: bool,
    only_power: bool,
    recurse: bool = False,
) -> None:
    """Plot IV-trace from file or directory containing shepherd-recordings."""
    files = path_to_flist(in_data, recurse=recurse)
    verbose_level = get_verbose_level()
    multiplot = multiplot and len(files) > 1
    data = []
    for file in files:
        logger.info("Generating plot for '%s' ...", file.name)
        try:
            with Reader(file, verbose=verbose_level > 2) as shpr:
                if multiplot:
                    date = shpr.generate_plot_data(start, end, relative_timestamp=True)
                    if date is None:
                        continue
                    data.append(date)
                else:
                    shpr.plot_to_file(start, end, width, height, only_pwr=only_power)
        except TypeError:
            logger.exception("ERROR: Will skip file. It caused an exception.")
    if multiplot:
        logger.info("Got %d datasets to plot", len(data))
        mpl_path = Reader.multiplot_to_file(data, in_data, width, height, only_pwr=only_power)
        if mpl_path:
            logger.info("Plot generated and saved to '%s'", mpl_path.name)
        else:
            logger.info("Plot not generated, path was already in use.")


if __name__ == "__main__":
    logger.info("This File should not be executed like this ...")
    cli()
