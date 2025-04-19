"""Content-Converters for firmwares."""

import base64
import hashlib
import shutil
from pathlib import Path
from typing import Union

import zstandard as zstd
from pydantic import validate_call

from ..data_models.content.firmware_datatype import FirmwareDType
from .converter_elf import elf_to_hex
from .validation import is_elf
from .validation import is_hex


@validate_call
def firmware_to_hex(file_path: Path) -> Path:
    """Convert ELF-Files to HEX.

    Generic converter that handles ELF & HEX.
    """
    if not file_path.is_file():
        raise FileNotFoundError("Fn needs an existing file as input")
    if is_elf(file_path):
        return elf_to_hex(file_path)
    if is_hex(file_path):
        return file_path
    raise FileNotFoundError("FW2Hex: unknown file '%s', it should be ELF or HEX", file_path.name)


@validate_call
def file_to_base64(file_path: Path) -> str:
    """Compress and encode content of file.

    - base64 adds ~33 % overhead
    - zstd compression reduces to ~ 1:3
    """
    if not file_path.is_file():
        raise ValueError("Fn needs an existing file as input")
    with file_path.resolve().open("rb") as file:
        file_content = file.read()
    file_cmpress = zstd.ZstdCompressor(level=20).compress(file_content)
    return base64.b64encode(file_cmpress).decode("ascii")


@validate_call
def base64_to_file(content: str, file_path: Path) -> None:
    """DeCompress and decode Content of file.

    - base64 adds ~33 % overhead
    - zstd compression reduces to ~ 1:3
    """
    file_cmpress = base64.b64decode(content)
    file_content = zstd.ZstdDecompressor().decompress(file_cmpress)
    if not file_path.parent.exists():
        file_path.parent.mkdir(parents=True)
    with file_path.resolve().open("wb") as file:
        file.write(file_content)


@validate_call
def file_to_hash(file_path: Path) -> str:
    """Convert file-content to hash-value."""
    if not file_path.is_file():
        raise ValueError("Fn needs an existing file as input")
    with file_path.resolve().open("rb") as file:
        file_content = file.read()
    return hashlib.sha3_224(file_content).hexdigest()


@validate_call
def base64_to_hash(content: str) -> str:
    """Convert base64-content to hash-value."""
    file_cmpress = base64.b64decode(content)
    file_content = zstd.ZstdDecompressor().decompress(file_cmpress)
    return hashlib.sha3_224(file_content).hexdigest()


@validate_call
def extract_firmware(data: Union[str, Path], data_type: FirmwareDType, file_path: Path) -> Path:
    """Make embedded firmware-data usable in filesystem.

    - base64-string will be transformed to file
    - if data is a path the file will be copied to the destination.
    """
    if data_type == FirmwareDType.base64_elf and isinstance(data, str):
        file = file_path.with_suffix(".elf")
        base64_to_file(data, file)
    elif data_type == FirmwareDType.base64_hex and isinstance(data, str):
        file = file_path.with_suffix(".hex")
        base64_to_file(data, file)
    elif isinstance(data, (Path, str)):
        if data_type == FirmwareDType.path_elf:
            file = file_path.with_suffix(".elf")
        elif data_type == FirmwareDType.path_hex:
            file = file_path.with_suffix(".hex")
        else:
            raise ValueError("FW-Extraction failed due to unknown datatype '%s'", data_type)
        if not file.parent.exists():
            file.parent.mkdir(parents=True)
        shutil.copy(data, file)
    else:
        raise ValueError("FW-Extraction failed due to unknown data-type '%s'", type(data))
    return file
