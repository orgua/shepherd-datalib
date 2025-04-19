"""Handling firmware for targets.

TODO: should be more generalized - currently only supports msp & nRF
"""

from pathlib import Path
from typing import Annotated
from typing import Optional
from typing import TypedDict
from typing import Union

from pydantic import StringConstraints
from pydantic import model_validator
from pydantic import validate_call
from typing_extensions import Self
from typing_extensions import Unpack

from ... import fw_tools
from ...logger import logger
from ...testbed_client import tb_client
from ..base.content import ContentModel
from ..testbed.mcu import MCU
from .firmware_datatype import FirmwareDType

suffix_to_DType: dict = {
    # derived from wikipedia
    ".hex": FirmwareDType.base64_hex,
    ".ihex": FirmwareDType.base64_hex,
    ".ihx": FirmwareDType.base64_hex,
    ".elf": FirmwareDType.base64_elf,
    ".bin": FirmwareDType.base64_elf,
    ".o": FirmwareDType.base64_elf,
    ".out": FirmwareDType.base64_elf,
    ".so": FirmwareDType.base64_elf,
}

base64_to_path_DType: dict = {
    FirmwareDType.base64_hex: FirmwareDType.path_hex,
    FirmwareDType.base64_elf: FirmwareDType.path_elf,
}

arch_to_mcu: dict = {
    "em_msp430": {"name": "msp430fr"},
    "msp430": {"name": "msp430fr"},
    "arm": {"name": "nrf52"},
    "nrf52": {"name": "nrf52"},
}

FirmwareStr = Annotated[str, StringConstraints(min_length=3, max_length=8_000_000)]


class Firmware(ContentModel, title="Firmware of Target"):
    """meta-data representation of a data-component."""

    # General Metadata & Ownership -> ContentModel

    mcu: MCU

    data: Union[FirmwareStr, Path]
    data_type: FirmwareDType
    data_hash: Optional[str] = None
    data_local: bool = True
    # ⤷ signals that file has to be copied to testbed

    @model_validator(mode="before")
    @classmethod
    def query_database(cls, values: dict) -> dict:
        values, _ = tb_client.try_completing_model(cls.__name__, values)
        # crosscheck type with actual data
        _type = values.get("data_type")
        if _type in {
            FirmwareDType.base64_hex,
            FirmwareDType.base64_elf,
        }:
            try:
                _hash = fw_tools.base64_to_hash(values.get("data"))
            except ValueError:
                raise ValueError("Embedded Firmware seems to be faulty") from None
            if values.get("data_hash") is not None and _hash != values.get("data_hash"):
                raise ValueError("Embedded Firmware and Hash do not match!")
        elif _type in {
            FirmwareDType.path_hex,
            FirmwareDType.path_elf,
        }:
            try:
                _ = Path(values.get("data"))
            except (SyntaxError, NameError):
                raise ValueError("Firmware-Path is invalid") from None
        return tb_client.fill_in_user_data(values)

    @classmethod
    def from_firmware(
        cls,
        file: Path,
        *,
        embed: bool = True,
        **kwargs: Unpack[TypedDict],
    ) -> Self:
        """Embeds firmware and tries to fill parameters.

        ELF -> mcu und data_type are deducted
        HEX -> must supply mcu manually.
        """
        # TODO: use new determine_type() & determine_arch() and also allow to not embed
        kwargs["data_hash"] = fw_tools.file_to_hash(file)
        if embed:
            kwargs["data"] = fw_tools.file_to_base64(file)
            kwargs["data_local"] = False
        else:
            kwargs["data"] = Path(file).as_posix()
            kwargs["data_local"] = True

        if "data_type" not in kwargs:
            kwargs["data_type"] = suffix_to_DType[file.suffix.lower()]

        if kwargs["data_type"] == FirmwareDType.base64_hex:
            if fw_tools.is_hex_msp430(file):
                arch = "msp430"
            elif fw_tools.is_hex_nrf52(file):
                arch = "nrf52"
            else:
                raise ValueError("File is not a suitable HEX for the Testbed")
            if "mcu" not in kwargs:
                kwargs["mcu"] = arch_to_mcu[arch]

        if kwargs["data_type"] == FirmwareDType.base64_elf:
            arch = fw_tools.read_arch(file)
            if "msp430" in arch and not fw_tools.is_elf_msp430(file):
                raise ValueError("File is not a ELF for msp430")
            if ("nrf52" in arch or "arm" in arch) and not fw_tools.is_elf_nrf52(file):
                raise ValueError("File is not a ELF for nRF52")
            logger.debug("ELF-File '%s' has arch: %s", file.name, arch)
            if "mcu" not in kwargs:
                kwargs["mcu"] = arch_to_mcu[arch]

        if not embed:
            kwargs["data_type"] = base64_to_path_DType[kwargs["data_type"]]

        if "name" not in kwargs:
            kwargs["name"] = file.name
        return cls(**kwargs)

    def compare_hash(self, path: Optional[Path] = None) -> bool:
        if self.data_hash is None:
            return True

        if path is not None and path.is_file():
            hash_new = fw_tools.file_to_hash(path)
            match = self.data_hash == hash_new
        else:
            hash_new = fw_tools.base64_to_hash(self.data)
            match = self.data_hash == hash_new

        if not match:
            logger.warning("FW-Hash does not match with stored value!")
            # TODO: it might be more appropriate to raise here
        return match

    @validate_call
    def extract_firmware(self, file: Path) -> Path:
        """Store embedded fw-data in file.

        - file-suffix is derived from data-type and adapted
        - if provided path is a directory, the firmware-name is used
        """
        if file.is_dir():
            file = file / self.name
        file_new = fw_tools.extract_firmware(self.data, self.data_type, file)
        self.compare_hash(file_new)
        return file_new
