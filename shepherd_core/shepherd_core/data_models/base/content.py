from datetime import datetime
from typing import Optional

from pydantic import Field
from pydantic import constr
from pydantic import root_validator

from .shepherd import ShpModel


class ContentModel(ShpModel):
    # General Properties
    id: constr(to_lower=True, max_length=16, regex=r"^[\w]*$") = Field(  # noqa: A003
        description="Unique ID (AlphaNum > 4 chars)",
    )
    name: constr(max_length=32, regex=r"^[ -~]*$")
    description: Optional[constr(regex=r"^[ -~]*$")] = Field(
        description="Required for public instances"
    )
    comment: Optional[constr(regex=r"^[ -~]*$")] = None
    created: datetime = Field(default_factory=datetime.now)

    # Ownership & Access
    owner: constr(max_length=32)
    group: constr(max_length=32) = Field(description="University or Subgroup")
    open2group: bool = False
    open2all: bool = False

    # The Regex
    # ^[\\w]*$    AlphaNum
    # ^[ -~]*$    All Printable ASCII-Characters with Space

    @root_validator(pre=False)
    def content_validation(cls, values: dict):
        is_open = values["open2group"] or values["open2all"]
        if is_open and isinstance(values["description"], type(None)):
            raise ValueError(
                "Public instances require a description "
                "(check open2*- and description-field)"
            )
        return values
