import os
from pathlib import Path
from typing import Optional

from elftools.common.exceptions import ELFError
from pwnlib.elf import ELF
from pydantic import conint
from pydantic import validate_arguments

from ..commons import uid_len_default
from ..commons import uid_str_default
from ..logger import logger as log


@validate_arguments
def find_symbol(file_elf: Path, symbol: str) -> bool:
    if symbol is None or not os.path.isfile(file_elf):
        return False
    try:
        elf = ELF(path=file_elf)
    except ELFError:
        log.debug(
            "File %s is not ELF - Magic number does not match", symbol, file_elf.name
        )
        return False

    try:
        elf.symbols[symbol]
    except KeyError:
        log.debug("Symbol '%s' not found in ELF-File %s", symbol, file_elf.name)
        return False
    log.debug(
        "Symbol '%s' found in ELF-File %s, arch=%s, order=%s",
        symbol,
        file_elf.name,
        elf.arch,
        elf.endian,
    )
    return True


@validate_arguments
def read_symbol(
    file_elf: Path, symbol: str, length: int = uid_len_default
) -> Optional[int]:
    """interpreted as int"""
    if not find_symbol(file_elf, symbol):
        return None
    elf = ELF(path=file_elf)
    addr = elf.symbols[symbol]
    value_raw = elf.read(address=addr, count=length)[-length:]
    return int.from_bytes(bytes=value_raw, byteorder=elf.endian, signed=False)


def read_uid(file_elf: Path) -> Optional[int]:
    return read_symbol(file_elf, symbol=uid_str_default, length=uid_len_default)


@validate_arguments
def modify_symbol_value(
    file_elf: Path,
    symbol: str,
    value: conint(ge=0, lt=2 ** (8 * uid_len_default)),
    overwrite: bool = False,
) -> Optional[Path]:
    """replaces value of symbol in ELF-File, hardcoded for uint16_t (2 byte)
    testbed uses FN to patch firmware with custom target-ID
    NOTE: overwrites provided file

    """
    if not find_symbol(file_elf, symbol):
        return None
    elf = ELF(path=file_elf)
    addr = elf.symbols[symbol]
    value_raw = elf.read(address=addr, count=uid_len_default)[-uid_len_default:]
    # cutting needed -> msp produces 4b instead of 2
    value_old = int.from_bytes(bytes=value_raw, byteorder=elf.endian, signed=False)
    value_raw = value.to_bytes(
        length=uid_len_default, byteorder=elf.endian, signed=False
    )
    elf.write(address=addr, data=value_raw)
    if overwrite:
        file_new = file_elf
    else:
        file_new = file_elf.with_stem(file_elf.stem + "_" + str(value))
    elf.save(path=file_new)
    elf.close()
    log.debug(
        "Value of Symbol '%s' modified: %s -> %s @%s",
        symbol,
        hex(value_old),
        hex(value),
        hex(addr),
    )
    return file_new


def modify_uid(file_elf: Path, value: int) -> Optional[Path]:
    return modify_symbol_value(
        file_elf, symbol=uid_str_default, value=value, overwrite=True
    )
