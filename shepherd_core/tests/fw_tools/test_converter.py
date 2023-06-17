from pathlib import Path

import pytest

from shepherd_core import fw_tools

from .conftest import files_elf


@pytest.mark.parametrize("path_elf", files_elf)
def test_elf_to_hex(path_elf: Path, tmp_path: Path) -> None:
    path_hex = (tmp_path / (path_elf.stem + ".hex")).resolve()
    path_gen = fw_tools.elf_to_hex(path_elf, path_hex)
    assert path_hex.exists()
    assert path_hex.as_posix() == path_gen.as_posix()


def test_hash() -> None:
    hash_a = fw_tools.file_to_hash(files_elf[0])
    hash_b = fw_tools.file_to_hash(files_elf[1])
    assert hash_a != hash_b


@pytest.mark.parametrize("path_elf", files_elf)
def test_base64(path_elf: Path, tmp_path: Path) -> None:
    b64_a = fw_tools.file_to_base64(path_elf)
    path_b = (tmp_path / path_elf.name).resolve()
    fw_tools.base64_to_file(b64_a, path_b)
    b64_b = fw_tools.file_to_base64(path_b)
    assert b64_a == b64_b
    hash_a = fw_tools.file_to_hash(path_elf)
    hash_b = fw_tools.file_to_hash(path_b)
    assert hash_a == hash_b