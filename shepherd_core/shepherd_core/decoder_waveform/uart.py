"""UART - Decoder.

Features:

- 1 bit Start (LOW)
- 1 .. **8** .. 64 bit data-frame
- **1**, 1.5, 2 bit stop (HIGH) - don't care?
- **no**, even, odd parity bit (there are more, see sigrok-link) - TODO
- **LSB** / MSB first - detectable with dict-compare - TODO
- **no** inversion

Todo:
- detect bitOrder
- detect dataframe length
- detect parity

More Info:

https://en.wikipedia.org/wiki/Universal_asynchronous_receiver-transmitter
https://sigrok.org/wiki/Protocol_decoder:Uart

"""

from enum import Enum
from pathlib import Path
from typing import Optional
from typing import Union

import numpy as np

from ..logger import logger


class Parity(str, Enum):
    """Options for parity-property of UART data-frame."""

    no = "no"
    even = "odd"
    odd = "even"


class BitOrder(str, Enum):
    """Options for bit-order-property of UART data-frame."""

    msb = msb_first = "msb"
    lsb = lsb_first = "lsb"


class Uart:
    """Specialized UART decoder."""

    def __init__(
        self,
        content: Union[Path, np.ndarray],
        baud_rate: Optional[int] = None,
        frame_length: Optional[int] = 8,
        inversion: Optional[bool] = None,
        parity: Optional[Parity] = Parity.no,
        bit_order: Optional[BitOrder] = BitOrder.lsb_first,
    ) -> None:
        """Provide a file with two columns: TS & Signal.

        Constraints:
        - timestamp -> seconds with fraction
        - signal -> can be analog or digital

        Note: class-parameters that are None (above) get auto-detected
          (some detectors still missing).
        """
        if isinstance(content, Path):
            self.events_sig: np.ndarray = np.loadtxt(content.as_posix(), delimiter=",", skiprows=1)
            # TODO: if float fails load as str -
            #  cast first col as np.datetime64 with ns-resolution, convert to delta
        else:
            self.events_sig = content

        # verify table
        if self.events_sig.shape[1] != 2:
            raise TypeError("Input file should have 2 rows -> (comma-separated) timestamp & value")
        if self.events_sig.shape[0] < 8:
            raise TypeError("Input file is too short (< state-changes)")
        # verify timestamps
        time_steps = self.events_sig[1:, 0] - self.events_sig[:-1, 0]
        if any(time_steps < 0):
            raise TypeError("Timestamps are not continuous")

        # prepare samples & process params (order is important)
        self._convert_analog2digital()
        self._filter_redundant_states()

        self.baud_rate: int = baud_rate if baud_rate is not None else self.detect_baud_rate()
        self.dur_tick: float = 1.0 / self.baud_rate

        self._add_duration()

        self.inversion: bool = inversion if inversion is not None else self.detect_inversion()
        self.half_stop: bool = self.detect_half_stop()  # not needed ATM

        # TODO: add detectors
        self.parity: Parity = parity if parity is not None else Parity.no
        self.bit_order: BitOrder = bit_order if bit_order is not None else BitOrder.lsb_first
        self.frame_length: int = frame_length if frame_length is not None else 8

        if not (0 < self.frame_length <= 64):
            raise ValueError("Dataframe length is out of bound (0, 64]")
        if self.parity != Parity.no:
            raise ValueError("Parities beside 'no' are not supported ATM")
        if self.bit_order != BitOrder.lsb_first:
            raise ValueError("Only bit-order LSB-first is supported ATM")

        if self.inversion:
            logger.debug("inversion was detected / issued -> will invert signal")
            self._convert_analog2digital(invert=True)
        if self.detect_inversion():
            logger.error("Signal still inverted?!? Check parameters and input")

        # results
        self.events_symbols: Optional[np.ndarray] = None
        self.events_lines: Optional[np.ndarray] = None
        self.text: Optional[str] = None

    def _convert_analog2digital(self, *, invert: bool = False) -> None:
        """Divide dimension in two, divided by mean-value."""
        data = self.events_sig[:, 1]
        mean = np.mean(data)
        if invert:
            self.events_sig[:, 1] = data <= mean
        else:
            self.events_sig[:, 1] = data >= mean

    def _filter_redundant_states(self) -> None:
        """Sum of two sequential states is always 1 (True + False) if alternating."""
        data_0 = self.events_sig[:, 1]
        data_1 = np.concatenate([[not data_0[0]], data_0[:-1]])
        data_f = data_0 + data_1
        self.events_sig = self.events_sig[data_f == 1]

        if len(data_0) > len(self.events_sig):
            logger.debug(
                "filtered out %d/%d events (redundant)",
                len(data_0) - len(self.events_sig),
                len(data_0),
            )

    def _add_duration(self) -> None:
        """Calculate third column -> duration of state in [baud-ticks]."""
        if self.events_sig.shape[1] > 2:
            logger.warning("Tried to add state-duration, but it seems already present")
            return
        if not hasattr(self, "dur_tick"):
            raise ValueError("Make sure that baud-rate was calculated before running add_dur()")
        dur_steps = self.events_sig[1:, 0] - self.events_sig[:-1, 0]
        dur_steps = np.reshape(dur_steps, (dur_steps.size, 1))
        self.events_sig = np.append(self.events_sig[:-1, :], dur_steps / self.dur_tick, axis=1)

    def detect_inversion(self) -> bool:
        """Analyze bit-state during long pauses (unchanged states).

        - pause should be HIGH for non-inverted mode (default)
        - assumes max frame size of 64 bit + x for safety
        """
        events = self.events_sig[:1000, :]  # speedup for large datasets
        pauses = events[:, 2] > 80
        states_1 = events[:, 1]
        pause_states = states_1[pauses]
        mean_state = pause_states.mean()
        if 0.1 < mean_state < 0.9:
            raise ValueError("Inversion in pauses could not be detected")
        return mean_state < 0.5

    def detect_baud_rate(self) -> int:
        """Analyze the smallest step."""
        events = self.events_sig[:1000, :]  # speedup for large datasets
        dur_steps = events[1:, 0] - events[:-1, 0]
        def_step = np.percentile(dur_steps[dur_steps > 0], 10)
        mean_tick = dur_steps[
            (dur_steps >= 0.66 * def_step) & (dur_steps <= 1.33 * def_step)
        ].mean()
        return round(1 / mean_tick)

    def detect_half_stop(self) -> bool:
        """Look into the spacing between time-steps to determine use of half stop."""
        events = self.events_sig[:1000, :]  # speedup for large datasets
        return np.sum((events > 1.333 * self.dur_tick) & (events < 1.667 * self.dur_tick)) > 0

    def detect_dataframe_length(self) -> int:
        """Try to determine length of dataframe.

        Algo will look for longest pauses & accumulate steps until
        a state with uneven step-size is found.
        """
        raise NotImplementedError

    def get_symbols(self, *, force_redo: bool = False) -> np.ndarray:
        """Extract symbols from events.

        Ways to detect EOF:
        - long pause on HIGH
        - off_tick pause on high
        - bit_pos > max

        # TODO:
            - slowest FN -> speedup with numba or parallelization?
            - dset could be divided (long pauses) and threaded for speedup.
        """
        if force_redo:
            self.events_symbols = None
        if self.events_symbols is not None:
            return self.events_symbols

        pos_df: Optional[int] = None
        symbol: int = 0
        t_start: Optional[float] = None
        content: list = []

        for time, value, steps in self.events_sig:
            if steps > self.frame_length:
                if value:
                    # long pause on High -> reset frame
                    if pos_df is not None:
                        content.append([t_start, chr(symbol)])
                        t_start = None
                        symbol = 0
                    pos_df = None
                else:
                    logger.debug("Error - Long pause - but SigLow (@%d)", time)
                continue
            if pos_df is None and value == 0:
                # Start of frame (first low after pause / EOF)
                pos_df = 0
                steps -= 1  # noqa: PLW2901
                t_start = time
            if pos_df is not None:
                if round(steps) >= 1 and value:
                    chunk = min(steps, self.frame_length - pos_df - 1)
                    lshift = min(pos_df, self.frame_length - 1)
                    symbol += (2 ** round(chunk) - 1) << lshift
                pos_df += round(steps)
                off_tick = abs(steps - round(steps)) > 0.1
                if pos_df >= self.frame_length or (off_tick and value):
                    # end of frame -> reset
                    if pos_df is not None:
                        content.append((t_start, chr(symbol)))
                        t_start = None
                        symbol = 0
                    pos_df = None
                    if off_tick and value == 0:
                        logger.debug("Error - Off-sized step - but SigLow (@%d)", time)
        self.events_symbols = np.concatenate(content).reshape((len(content), 2))
        # TODO: numpy is converting timestamp to string -> must be added as tuple (ts, symbol)
        # symbol_events[:, 0] = symbol_events[:, 0].astype(float)  # noqa: ERA001
        # ⤷ does not work
        return self.events_symbols

    def get_lines(self, *, force_redo: bool = False) -> np.ndarray:
        r"""Timestamped symbols to line, cut at \r, \r\n or \n."""
        if force_redo:
            self.events_lines = None
        if self.events_lines is not None:
            return self.events_lines
        if self.events_symbols is None:
            self.get_symbols()

        content = []
        semi_stop = False
        t_start = None
        line = ""
        for time, symbol in self.events_symbols:
            if symbol == "\n" or semi_stop:
                if symbol == "\n":
                    line += symbol
                content.append((t_start, line))
                semi_stop = False
                t_start = None
                line = ""
                if not semi_stop:
                    continue
            if symbol == "\r":
                semi_stop = True

            if t_start is None:
                t_start = time
            line += symbol
        self.events_lines = np.concatenate(content).reshape((len(content), 2))
        return self.events_lines

    def get_text(self, *, force_redo: bool = False) -> str:
        """Remove timestamps and just return the whole string."""
        if force_redo:
            self.text = None
        if self.text is not None:
            return self.text
        if self.events_lines is None:
            self.get_lines()
        self.text = "".join(self.events_lines[:, 1])
        return self.text
