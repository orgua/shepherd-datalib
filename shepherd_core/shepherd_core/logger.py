"""Log handler of shepherd."""

import logging
import logging.handlers
from typing import Union

import chromalog

chromalog.basicConfig(format="%(message)s")
logger = logging.getLogger("SHPCore")
logger.addHandler(logging.NullHandler())

verbose_level: int = 2


def get_verbose_level() -> int:
    """Get log level of shepherd."""
    return verbose_level


def set_log_verbose_level(log_: Union[logging.Logger, logging.Handler], verbose: int) -> None:
    """Set log level of shepherd."""
    if verbose == 0:
        log_.setLevel(logging.ERROR)
        logging.basicConfig(level=logging.ERROR)
    elif verbose == 1:
        log_.setLevel(logging.WARNING)
    elif verbose == 2:
        log_.setLevel(logging.INFO)
    elif verbose > 2:
        log_.setLevel(logging.DEBUG)

    if verbose < 3:
        # reduce log-overhead when not debugging, also more user-friendly exceptions
        logging._srcfile = None  # noqa: SLF001
        logging.logThreads = False
        logging.logProcesses = False

    if verbose > 2:
        chromalog.basicConfig(format="%(name)s %(levelname)s: %(message)s")
    else:
        chromalog.basicConfig(format="%(message)s")  # reduce internals


def increase_verbose_level(verbose: int) -> None:
    """Increase log level of shepherd."""
    global verbose_level  # noqa: PLW0603
    if verbose >= verbose_level:
        verbose_level = min(max(verbose, 0), 3)
        set_log_verbose_level(logger, verbose_level)


increase_verbose_level(2)

# short reminder for format-strings:
# %s    string
# %d    decimal
# %f    float
# %o    decimal as octal
# %x    decimal as hex
#
# %05d  pad right (aligned with 5chars)
# %-05d pad left (left aligned)
# %06.2f    6chars float, including dec point, with 2 chars after
# %.5s  truncate to 5 chars
#
# %% for a percent character
