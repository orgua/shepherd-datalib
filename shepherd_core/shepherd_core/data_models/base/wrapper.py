"""Wrapper-related ecosystem for transferring models."""

from datetime import datetime
from typing import Annotated
from typing import Optional

from pydantic import BaseModel
from pydantic import StringConstraints

from ...version import version

SafeStrClone = Annotated[str, StringConstraints(pattern=r"^[ -~]+$")]
# ⤷ copy avoids circular import


class Wrapper(BaseModel):
    """Generalized web- & file-interface for all models with dynamic typecasting."""

    datatype: str
    # ⤷ model-name
    comment: Optional[SafeStrClone] = None
    created: Optional[datetime] = None
    # ⤷ Optional metadata
    lib_ver: Optional[str] = version
    # ⤷ for debug-purposes and later comp-checks
    parameters: dict
    # ⤷ ShpModel
