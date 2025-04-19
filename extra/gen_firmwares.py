"""This script will download & prepare target-firmwares.

- download and extract firmwares from https://github.com/orgua/shepherd-targets/releases
- generate embedded firmware-models
- it assumes sub-dirs in the same dir with ./build.elf in it
"""

import shutil
from io import BytesIO
from pathlib import Path
from urllib.request import urlopen
from zipfile import ZipFile

import yaml

from shepherd_core.data_models.content.firmware import Firmware
from shepherd_core.logger import logger

if __name__ == "__main__":
    path_here = Path(__file__).parent.absolute()
    if Path("/var/shepherd/").exists():
        path_fw = Path("/var/shepherd/content/fw/nes_lab/")
    else:
        path_fw = path_here / "content/fw/nes_lab/"

    # config
    link = "https://github.com/orgua/shepherd-targets/releases/latest/download/firmwares.zip"
    # ⤷ already includes embedded-firmware-models
    path_meta = path_fw / "metadata_fw.yaml"

    logger.info("Downloading latest release")
    data = urlopen(link).read()  # noqa: S310
    logger.info("Unpacking Archive")
    with ZipFile(BytesIO(data), "r") as zip_ref:
        zip_ref.extractall(path_here / "temp")

    shutil.move(path_here / "temp/content", path_fw)

    if not path_meta.exists():
        logger.error("Metadata-file not found, will stop (%s)", path_meta.as_posix())
    else:
        with path_meta.open() as file_meta:
            metadata = yaml.safe_load(file_meta)["metadata"]

        for _fw, _descr in metadata.items():
            path_sub = path_fw / _fw
            files_elf = [each for each in path_sub.iterdir() if each.endswith(".elf")]

            if len(files_elf) > 1:
                logger.warning("More than one .ELF in directory -> will use first of %s", files_elf)
            path_elf = path_sub / files_elf[0]

            if path_elf.exists():
                Firmware.from_firmware(
                    file=path_elf,
                    embed=False,
                    name=_fw,
                    description=_descr,
                    owner="Ingmar",
                    group="NES_Lab",
                    visible2group=True,
                    visible2all=True,
                ).to_file(path_elf.with_suffix(".yaml"))
                logger.info("saved FW %s", path_elf)
            else:
                logger.error("FW not found, will skip: %s", path_elf.as_posix())

            # debug-part below
            sizeof: dict[str, int] = {}
            sizeof["elf"] = path_elf.stat().st_size
            files_hex = [each for each in path_sub.iterdir() if each.endswith(".hex")]
            if files_hex:
                sizeof["hex"] = (path_sub / files_hex[0]).stat().st_size
            file_temp = path_here / "temp" / "demo_fw.yaml"
            fw = Firmware.from_firmware(path_elf)
            fw.to_file(file_temp, minimal=True)
            sizeof["yaml"] = file_temp.stat().st_size
            with file_temp.open("w") as fh:
                fh.write(fw.model_dump_json(exclude_unset=True, exclude_defaults=True))
            sizeof["json"] = file_temp.stat().st_size
            logger.info(" -> size-stat: %s", sizeof)
