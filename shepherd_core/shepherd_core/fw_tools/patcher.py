"""Read and modify symbols in ELF-files."""

from pathlib import Path
from typing import Annotated
from typing import Optional

from pydantic import Field
from pydantic import validate_call

from ..commons import uid_len_default
from ..commons import uid_str_default
from ..logger import logger
from .validation import is_elf

try:
    from pwnlib.elf import ELF
except ImportError as e:
    ELF = None
    elf_error_text = (
        "Please install functionality with 'pip install shepherd-core[elf] -U' first, "
        f"underlying exception: {e.msg}"
    )


@validate_call
def find_symbol(file_elf: Path, symbol: str) -> bool:
    """Find a symbol in the ELF file."""
    if symbol is None or not is_elf(file_elf):
        return False
    if ELF is None:
        raise RuntimeError(elf_error_text)
    elf = ELF(path=file_elf)
    try:
        addr = elf.symbols[symbol]
    except KeyError:
        addr = None
    if addr is None:
        logger.debug("Symbol '%s' not found in ELF-File %s", symbol, file_elf.name)
        return False
    logger.debug(
        "Symbol '%s' found in ELF-File %s, arch=%s, order=%s",
        symbol,
        file_elf.name,
        elf.arch,
        elf.endian,
    )
    elf.close()
    return True


@validate_call
def read_symbol(file_elf: Path, symbol: str, length: int = uid_len_default) -> Optional[int]:
    """Read value of symbol in ELF-File.

    Will be interpreted as int.
    """
    if not find_symbol(file_elf, symbol):
        return None
    if ELF is None:
        raise RuntimeError(elf_error_text)
    elf = ELF(path=file_elf)
    addr = elf.symbols[symbol]
    value_raw = elf.read(address=addr, count=length)[-length:]
    elf.close()
    return int.from_bytes(bytes=value_raw, byteorder=elf.endian, signed=False)


def read_uid(file_elf: Path) -> Optional[int]:
    """Read value of UID-symbol for shepherd testbed."""
    return read_symbol(file_elf, symbol=uid_str_default, length=uid_len_default)


def read_arch(file_elf: Path) -> Optional[str]:
    """Determine chip-architecture from elf-metadata."""
    if not is_elf(file_elf):
        return None
    if ELF is None:
        raise RuntimeError(elf_error_text)
    elf = ELF(path=file_elf)
    if "exec" in elf.elftype.lower():
        return elf.arch.lower()
    logger.error("ELF is not Executable")
    return None


@validate_call
def modify_symbol_value(
    file_elf: Path,
    symbol: str,
    value: Annotated[int, Field(ge=0, lt=2 ** (8 * uid_len_default))],
    *,
    overwrite: bool = False,
) -> Optional[Path]:
    """Replace value of uint16-symbol in ELF-File.

    Hardcoded for uint16_t (2 byte).
    The testbed uses this to patch firmware with custom target-ID.

    NOTE: can overwrite provided file.

    """
    if not find_symbol(file_elf, symbol):
        return None
    if ELF is None:
        raise RuntimeError(elf_error_text)
    elf = ELF(path=file_elf)
    addr = elf.symbols[symbol]
    value_raw = elf.read(address=addr, count=uid_len_default)[-uid_len_default:]
    # ⤷ cutting needed -> msp produces 4b instead of 2
    value_old = int.from_bytes(bytes=value_raw, byteorder=elf.endian, signed=False)
    value_raw = value.to_bytes(length=uid_len_default, byteorder=elf.endian, signed=False)

    try:
        elf.write(address=addr, data=value_raw)
    except AttributeError:
        logger.warning("ELF-Modifier failed @%s for symbol '%s'", f"0x{addr:X}", symbol)
        return None

    file_new = file_elf if overwrite else file_elf.with_stem(file_elf.stem + "_" + str(value))
    elf.save(path=file_new)
    elf.close()
    logger.debug(
        "Value of Symbol '%s' modified: %s -> %s @%s",
        symbol,
        hex(value_old),
        hex(value),
        hex(addr),
    )
    return file_new


def modify_uid(file_elf: Path, value: int) -> Optional[Path]:
    """Replace value of UID-symbol for shepherd testbed."""
    return modify_symbol_value(file_elf, symbol=uid_str_default, value=value, overwrite=True)
