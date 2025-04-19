"""Shepherds base-model that brings a lot of default functionality."""

import hashlib
import pathlib
from collections.abc import Generator
from datetime import timedelta
from ipaddress import IPv4Address
from pathlib import Path
from typing import Any
from typing import Optional
from typing import Union
from uuid import UUID

import yaml
from pydantic import BaseModel
from pydantic import ConfigDict
from typing_extensions import Self
from yaml import Node
from yaml import SafeDumper

from .timezone import local_now
from .wrapper import Wrapper


def path2str(
    dumper: SafeDumper, data: Union[pathlib.Path, pathlib.WindowsPath, pathlib.PosixPath]
) -> Node:
    """Add a yaml-representation for a specific datatype."""
    return dumper.represent_scalar("tag:yaml.org,2002:str", str(data.as_posix()))


def time2int(dumper: SafeDumper, data: timedelta) -> Node:
    """Add a yaml-representation for a specific datatype."""
    return dumper.represent_scalar("tag:yaml.org,2002:int", str(int(data.total_seconds())))


def generic2str(dumper: SafeDumper, data: Any) -> Node:
    """Add a yaml-representation for a specific datatype."""
    return dumper.represent_scalar("tag:yaml.org,2002:str", str(data))


yaml.add_representer(pathlib.PosixPath, path2str, SafeDumper)
yaml.add_representer(pathlib.WindowsPath, path2str, SafeDumper)
yaml.add_representer(pathlib.Path, path2str, SafeDumper)
yaml.add_representer(timedelta, time2int, SafeDumper)
yaml.add_representer(IPv4Address, generic2str, SafeDumper)
yaml.add_representer(UUID, generic2str, SafeDumper)


class ShpModel(BaseModel):
    """Pre-configured Pydantic Base-Model (specifically for shepherd).

    Inheritable Features:
    - constant / frozen, hashable .get_hash()
    - safe / limited custom types
    - string-representation str(ShpModel)
    - accessible as class (model.var) and dict (model[var])
    - yaml-support with type-safe .from_file() & .to_file()
        - stores minimal set (filters out unset & default parameters)
    - schema cls.schema() can also be stored to yaml with .schema_to_file()
    """

    model_config = ConfigDict(
        frozen=True,  # -> const after creation, hashable! but currently manually with .get_hash()
        extra="forbid",  # no unnamed attributes allowed
        validate_default=True,
        validate_assignment=True,  # not relevant for the frozen model
        str_min_length=1,  # force more meaningful descriptors,
        # ⤷ TODO: was 4 but localizing constraints works different with pydantic2
        #       - might be solvable with "use_enum_values=True"
        str_max_length=512,
        # ⤷ local str-length constraints overrule global ones!
        str_strip_whitespace=True,  # strip leading & trailing whitespaces
        use_enum_values=True,  # cleaner export of enum-parameters
        allow_inf_nan=False,  # float without +-inf or NaN
        # defer_build=True, possible speedup -> but it triggers a bug
    )

    def __repr__(self) -> str:
        """string-representation allows print(model)."""
        name = type(self).__name__
        content = self.model_dump(exclude_unset=True, exclude_defaults=True)
        return f"{name}({content})"

    def __str__(self) -> str:
        """string-representation allows str(model)."""
        content = yaml.safe_dump(
            self.model_dump(exclude_unset=True, exclude_defaults=True),
            default_flow_style=False,
            sort_keys=False,
        )
        return str(content)

    def __getitem__(self, key: str) -> Any:
        """Allow dict access like model["key"].

        in addition to model.key.
        """
        return self.__getattribute__(key)

    def __contains__(self, item: str) -> bool:
        """Allow checks like 'x in YClass'."""
        return item in self.model_dump().keys()  # noqa: SIM118
        # more correct, but probably slower than hasattr

    def keys(self):  # noqa: ANN201
        """Fn of dict."""
        return self.model_dump().keys()

    def items(self) -> Generator[tuple, None, None]:
        """Fn of dict."""
        for key in self.keys():
            yield key, self[key]

    @classmethod
    def schema_to_file(cls, path: Union[str, Path]) -> None:
        """Store schema to yaml (for frontend-generators)."""
        model_dict = cls.model_json_schema()
        model_yaml = yaml.safe_dump(model_dict, default_flow_style=False, sort_keys=False)
        with Path(path).resolve().with_suffix(".yaml").open("w") as f:
            f.write(model_yaml)

    def to_file(
        self,
        path: Union[str, Path],
        comment: Optional[str] = None,
        *,
        minimal: bool = True,
    ) -> Path:
        """Store data to yaml in a wrapper.

        minimal: stores minimal set (filters out unset & default parameters)
        comment: documentation.
        """
        model_dict = self.model_dump(exclude_unset=minimal)
        model_wrap = Wrapper(
            datatype=type(self).__name__,
            comment=comment,
            created=local_now(),
            parameters=model_dict,
        )
        model_yaml = yaml.safe_dump(
            model_wrap.model_dump(exclude_unset=minimal, exclude_defaults=minimal),
            default_flow_style=False,
            sort_keys=False,
        )
        # TODO: handle directory
        model_path = Path(path).resolve().with_suffix(".yaml")
        if not model_path.parent.exists():
            model_path.parent.mkdir(parents=True)
        with model_path.open("w") as f:
            f.write(model_yaml)
        return model_path

    @classmethod
    def from_file(cls, path: Union[str, Path]) -> Self:
        """Load from yaml."""
        with Path(path).open() as shp_file:
            shp_dict = yaml.safe_load(shp_file)
        shp_wrap = Wrapper(**shp_dict)
        if shp_wrap.datatype != cls.__name__:
            raise ValueError("Model in file does not match the requirement")
        return cls(**shp_wrap.parameters)

    def get_hash(self) -> str:
        return hashlib.sha3_224(str(self.model_dump()).encode("utf-8")).hexdigest()
