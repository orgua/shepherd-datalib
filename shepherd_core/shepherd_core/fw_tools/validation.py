""" TODO: Work in Progress

"""
import os
import tempfile
from pathlib import Path

from intelhex import IntelHex
from intelhex import IntelHexError
from pydantic import validate_arguments

from ..data_models.content.firmware_datatype import FirmwareDType
from ..logger import logger
from .converter_elf import elf_to_hex

try:
    from elftools.common.exceptions import ELFError
    from pwnlib.elf import ELF

    elf_support = True
except ImportError:
    elf_support = False


@validate_arguments
def is_hex(file: Path):
    try:
        _ = IntelHex(file.as_posix())
    except ValueError:  # parsing
        return False
    except IntelHexError:  # structural errors
        return False
    return True


def is_hex_msp430(file: Path):
    """Observations:
    - addresses begin at 0x4000
    - value @0xFFFE (IVT) is start_address (of pgm-code)
    """
    if is_hex(file):
        ih = IntelHex(file.as_posix())
        if ih.minaddr() != 0x4000:
            return False
        if 0xFFFE not in ih.addresses():
            return False
        value = int.from_bytes(ih.gets(0xFFFE, 2), byteorder="little", signed=False)
        if 0x4000 > value >= 0xFF80:
            return False
        if ih.get_memory_size() >= 270_000:
            # conservative test for now - should be well below 128 kB + 8kB for msp430fr5962
            return False
        return True
    return False


def is_hex_nrf52(file: Path) -> bool:
    """Observations:
    - addresses begin at 0x0
    - only one segment (.get_segments), todo
    """
    if is_hex(file):
        ih = IntelHex(file.as_posix())
        if ih.minaddr() != 0x0000:
            return False
        if ih.get_memory_size() >= 1310720:
            # conservative test for now - should be well below 1 MB + 256 kB
            return False
        return True
    return False


# TODO: elf-workflow needs work -> construct experiments without external dependencies
#  - remove conversion to hex
#  - use elftools to verify magic-bytes and similar things done for the hex
#  https://github.com/eliben/pyelftools/wiki/User's-guide


@validate_arguments
def is_elf(file: Path) -> bool:
    if not elf_support:
        raise RuntimeError(
            "Please install functionality with "
            "'pip install shepherd_core[elf] -U' first"
        )
    if not os.path.isfile(file):
        return False
    try:
        _ = ELF(path=file)
    except ELFError:
        logger.debug("File %s is not ELF - Magic number does not match", file.name)
        return False
    return True


def is_elf_msp430(file: Path) -> bool:
    if is_elf(file):
        with tempfile.TemporaryDirectory() as path:
            file_hex = Path(path) / "file.hex"
            file_hex = elf_to_hex(file, file_hex)
            if is_hex_msp430(file_hex):
                return True
        return False
    return False


def is_elf_nrf52(file: Path) -> bool:
    if is_elf(file):
        with tempfile.TemporaryDirectory() as path:
            file_hex = Path(path) / "file.hex"
            file_hex = elf_to_hex(file, file_hex)
            if is_hex_nrf52(file_hex):
                return True
        return False
    return False


def determine_type(file: Path) -> FirmwareDType:
    if not file.is_file():
        raise ValueError("Fn needs an existing file as input")
    if is_hex(file):
        return FirmwareDType.path_hex
    elif is_elf(file):
        return FirmwareDType.path_elf
    raise ValueError("Type of file '%s' could not be determined", file.name)


def determine_arch(file: Path) -> str:
    file_t = determine_type(file)
    if file_t == FirmwareDType.path_elf:
        if is_elf_nrf52(file):
            return "nrf52"
        elif is_elf_msp430(file):
            return "msp430"
        raise ValueError("Arch of ELF '%s' could not be determined", file.name)
    elif file_t == FirmwareDType.path_hex:
        if is_hex_nrf52(file):
            return "nrf52"
        elif is_hex_msp430(file):
            return "msp430"
        raise ValueError("Arch of HEX '%s' could not be determined", file.name)
    raise ValueError("Arch of file '%s' could not be determined", file.name)
