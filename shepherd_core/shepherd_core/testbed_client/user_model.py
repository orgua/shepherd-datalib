"""Model for user-management."""

import secrets
from hashlib import pbkdf2_hmac
from typing import Annotated
from typing import Optional
from typing import Union
from uuid import uuid4

from pydantic import UUID4
from pydantic import EmailStr
from pydantic import Field
from pydantic import SecretBytes
from pydantic import SecretStr
from pydantic import StringConstraints
from pydantic import model_validator
from pydantic import validate_call

from ..data_models.base.content import NameStr
from ..data_models.base.content import SafeStr
from ..data_models.base.shepherd import ShpModel


@validate_call
def hash_password(pw: Annotated[str, StringConstraints(min_length=20, max_length=100)]) -> bytes:
    """Generate a hash of a string.

    # NOTE: 1M Iterations need 25s on beaglebone
    # TODO: add salt of testbed -> this fn should be part of Testbed-Object
    """
    return pbkdf2_hmac(
        "sha512",
        password=pw.encode("utf-8"),
        salt=b"testbed_salt_TODO",
        iterations=1_000_000,
        dklen=128,
    )


class User(ShpModel):
    """meta-data representation of a testbed-component (physical object)."""

    # id: UUID4 = Field(  # TODO: db-migration - temp fix for documentation
    id: Union[UUID4, int] = Field(
        description="Unique ID",
        default_factory=uuid4,
    )
    name: NameStr
    description: Optional[SafeStr] = None
    comment: Optional[SafeStr] = None

    name_full: Optional[NameStr] = None
    group: NameStr
    email: EmailStr

    pw_hash: Optional[SecretBytes] = None
    # ⤷ was hash_password("this_will_become_a_salted_slow_hash") -> slowed BBB down
    # ⤷ TODO (min_length=128, max_length=512)

    token: SecretStr
    # ⤷ TODO (min_length=128), request with: token.get_secret_value()
    active: bool = False

    @model_validator(mode="before")
    @classmethod
    def query_database(cls, values: dict) -> dict:
        # TODO:

        # post correction
        if values.get("token") is None:
            values["token"] = "shepherd_token_" + secrets.token_urlsafe(nbytes=128)

        return values
