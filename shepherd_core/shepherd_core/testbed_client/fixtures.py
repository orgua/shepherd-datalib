import copy
import os
from pathlib import Path
from typing import Dict
from typing import Optional

import yaml

from ..data_models.base.wrapper import Wrapper
from ..logger import logger

# Proposed field-name:
# - inheritance
# - inherit_from  <-- current choice
# - inheritor
# - hereditary
# - based_on


class Fixture:
    """Current implementation of a file-based database"""

    def __init__(self, model_type: str):
        self.model_type: str = model_type.lower()
        self.elements_by_name: Dict[str, dict] = {}
        self.elements_by_id: Dict[int, dict] = {}
        # Iterator reset
        self._iter_index: int = 0
        self._iter_list: list = list(self.elements_by_name.values())

    def insert(self, data: Wrapper) -> None:
        # ⤷ TODO: could get easier
        #    - when not model_name but class used
        #    - use doubleref name->id->data (safes RAM)
        if data.datatype.lower() != self.model_type.lower():
            return
        if "name" not in data.parameters:
            return
        name = str(data.parameters["name"]).lower()
        _id = data.parameters["id"]
        data = data.parameters
        self.elements_by_name[name] = data
        self.elements_by_id[_id] = data
        # update iterator
        self._iter_list: list = list(self.elements_by_name.values())

    def __getitem__(self, key) -> dict:
        key = key.lower()
        if key in self.elements_by_name:
            return self.elements_by_name[key]
        if key in self.elements_by_id:
            return self.elements_by_id[key]
        raise ValueError(f"{self.model_type} '{key}' not found!")

    def __iter__(self):
        self._iter_index = 0
        self._iter_list = list(self.elements_by_name.values())
        return self

    def __next__(self):
        if self._iter_index < len(self._iter_list):
            member = self._iter_list[self._iter_index]
            self._iter_index += 1
            return member
        raise StopIteration

    def keys(self):  # -> _dict_keys[Any, Any]:
        return self.elements_by_name.keys()

    def refs(self) -> dict:
        return {_i["id"]: _i["name"] for _i in self.elements_by_id.values()}

    def inheritance(self, values: dict, chain: Optional[list] = None) -> (dict, list):
        if chain is None:
            chain = []
        values = copy.copy(values)
        post_process: bool = False
        fixture_base: dict = {}
        if "inherit_from" in values:
            fixture_name = values.pop("inherit_from")
            # ⤷ will also remove entry from dict
            if "name" in values and len(chain) < 1:
                base_name = values.get("name")
                if base_name in chain:
                    raise ValueError(
                        f"Inheritance-Circle detected ({base_name} already in {chain})",
                    )
                if base_name == fixture_name:
                    raise ValueError(
                        f"Inheritance-Circle detected ({base_name} == {fixture_name})",
                    )
                chain.append(base_name)
            fixture_base = copy.copy(self[fixture_name])
            logger.debug("'%s' will inherit from '%s'", self.model_type, fixture_name)
            fixture_base["name"] = fixture_name
            chain.append(fixture_name)
            base_dict, chain = self.inheritance(values=fixture_base, chain=chain)
            for key, value in values.items():
                # keep previous entries
                base_dict[key] = value
            values = base_dict

        # TODO: cleanup and simplify - use fill_mode() and line up with web-interface
        elif "name" in values and values.get("name").lower() in self.elements_by_name:
            fixture_name = values.get("name").lower()
            fixture_base = copy.copy(self.elements_by_name[fixture_name])
            post_process = True

        elif values.get("id") in self.elements_by_id:
            _id = values["id"]
            fixture_base = copy.copy(self.elements_by_id[_id])
            post_process = True

        if post_process:
            # last two cases need
            for key, value in values.items():
                # keep previous entries
                fixture_base[key] = value
            if "inherit_from" in fixture_base:
                # as long as this key is present this will act recursively
                chain.append(fixture_base["name"])
                values, chain = self.inheritance(values=fixture_base, chain=chain)
            else:
                values = fixture_base

        return values, chain

    @staticmethod
    def fill_model(model: dict, base: dict) -> dict:
        base = copy.copy(base)
        for key, value in model.items():
            # keep previous entries
            base[key] = value
        return base

    def query_id(self, _id: int) -> dict:
        if isinstance(_id, int) and _id in self.elements_by_id:
            return self.elements_by_id[_id]
        else:
            raise ValueError(
                f"Initialization of {self.model_type} by ID failed - {_id} is unknown!"
            )

    def query_name(self, name: str):
        if isinstance(name, str) and name.lower() in self.elements_by_name:
            return self.elements_by_name[name.lower()]
        else:
            raise ValueError(
                f"Initialization of {self.model_type} by name failed - {name} is unknown!"
            )


class Fixtures:
    suffix = ".yaml"

    def __init__(self, file_path: Optional[Path] = None):
        if file_path is None:
            self.file_path = Path(__file__).parent.parent.resolve() / "data_models"
        else:
            self.file_path = file_path
        self.components: Dict[str, Fixture] = {}

        if self.file_path.is_file():
            files = [self.file_path]
        elif self.file_path.is_dir():
            files = get_files(self.file_path, self.suffix)
        else:
            raise ValueError("Path must either be file or directory (or empty)")

        for file in files:
            self.insert_file(file)

    def insert_file(self, file: Path):
        with open(file) as fd:
            fixtures = yaml.safe_load(fd)
            for fixture in fixtures:
                if not isinstance(fixture, dict):
                    continue
                fix_wrap = Wrapper(**fixture)
                self.insert_model(fix_wrap)

    def insert_model(self, data: Wrapper):
        fix_type = data.datatype.lower()
        if self.components.get(fix_type) is None:
            self.components[fix_type] = Fixture(model_type=fix_type)
        self.components[fix_type].insert(data)

    def __getitem__(self, key) -> Fixture:
        key = key.lower()
        if key in self.components:
            return self.components[key]
        raise ValueError(f"Component '{key}' not found!")

    def keys(self):  # -> _dict_keys[Any, Any]:
        return self.components.keys()

    def to_file(self, file: Path):
        raise RuntimeError("Not Implemented, TODO")


def get_files(start_path: Path, suffix: str, recursion_depth: int = 0) -> list:
    if recursion_depth == 0:
        suffix = suffix.lower().split(".")[-1]
    dir_items = os.scandir(start_path)
    recursion_depth += 1
    files = []

    for item in dir_items:
        if item.is_dir():
            files += get_files(item.path, suffix, recursion_depth)
            continue
        else:
            item_name = str(item.name).lower()
            item_ext = item_name.split(".")[-1]
            if item_ext == suffix and item_ext != item_name:
                files.append(item.path)
            if suffix == "" and item_ext == item_name:
                files.append(item.path)
    if recursion_depth == 1 and len(files) > 0:
        logger.debug(" -> got %s files with the suffix '%s'", len(files), suffix)
    return files