"""Client-Class to access a testbed instance over the web."""

from importlib import import_module
from pathlib import Path
from typing import Optional
from typing import Union

from pydantic import validate_call

from ..commons import testbed_server_default
from ..data_models.base.shepherd import ShpModel
from ..data_models.base.wrapper import Wrapper
from .client_abc_fix import AbcClient
from .user_model import User


class WebClient(AbcClient):
    """Client-Class to access a testbed instance over the web.

    For online-queries the lib can be connected to the testbed-server.
    NOTE: there are 3 states:
    - unconnected -> demo-fixtures are queried (locally)
    - connected -> publicly available data is queried online
    - logged in with valid token -> also private data is queried online
    """

    testbed_server_default = "https://shepherd.cfaed.tu-dresden.de:8000/testbed"

    def __init__(self, server: Optional[str] = None, token: Union[str, Path, None] = None) -> None:
        """Connect to Testbed-Server with optional token and server-address.

        server: optional address to shepherd-server-endpoint
        token: your account validation. if omitted, only public data is available
        """
        super().__init__()
        if not hasattr(self, "_token"):
            # add default values
            self._token: str = "basic_public_access"  # noqa: S105
            self._server: str = testbed_server_default
            self._user: Optional[User] = None
            self._key: Optional[str] = None
            self._connected: bool = False
            self._req = None

        if not self._connected:
            self._connect(server, token)

    # ABC Functions below

    def insert(self, data: ShpModel) -> bool:
        if self._req is None:
            return False
        wrap = Wrapper(
            datatype=type(data).__name__,
            parameters=data.model_dump(),
        )
        r = self._req.post(self._server + "/add", data=wrap.model_dump_json(), timeout=2)
        r.raise_for_status()
        return True

    def query_ids(self, model_type: str) -> list[int]:
        raise NotImplementedError("TODO")

    def query_names(self, model_type: str) -> list[str]:
        raise NotImplementedError("TODO")

    def query_item(
        self, model_type: str, uid: Optional[int] = None, name: Optional[str] = None
    ) -> dict:
        raise NotImplementedError("TODO")

    def try_inheritance(self, model_type: str, values: dict) -> tuple[dict, list]:
        raise NotImplementedError("TODO")

    def fill_in_user_data(self, values: dict) -> dict:
        if self._user is None:
            return values
        if values.get("owner") is None:
            values["owner"] = self._user.name
        if values.get("group") is None:
            values["group"] = self._user.group
        return values

    # Below are extra FNs not in ABC

    @validate_call
    def _connect(self, server: Optional[str] = None, token: Union[str, Path, None] = None) -> bool:
        """Establish connection to testbed-server.

        TODO: totally not finished
        """
        if isinstance(token, Path):
            if not token.exists():
                raise FileNotFoundError("Token-Path does not exist")
            with token.resolve().open() as file:
                self._token = file.read()
        elif isinstance(token, str):
            self._token = self._token

        if isinstance(server, str):
            self._server = server.lower()

        self._req = import_module("requests")  # here due to slow startup

        # extended connection-test:
        self._query_session_key()
        self._connected = True
        return self._query_user_data()

    def _query_session_key(self) -> bool:
        if self._server and self._req is not None:
            r = self._req.get(self._server + "/session_key", timeout=2)
            r.raise_for_status()
            self._key = r.json()["value"]  # TODO: not finished
            return True
        return False

    def _query_user_data(self) -> bool:
        if self._server and self._req is not None:
            r = self._req.get(self._server + "/user?token=" + self._token, timeout=2)
            # TODO: possibly a security nightmare (send via json or encrypted via public key?)
            r.raise_for_status()
            self._user = User(**r.json())
            return True
        return False

    def submit_experiment(self, xp: ShpModel) -> str:
        """Transmit XP to server to validate its feasibility.

        - Experiment will be added to DB (if not present)
            - if the same experiment is resubmitted it will just return the ID of that XP
        - Experiment will be validated by converting it into a task-set (additional validation)
        - optional: the scheduler should validate there are no time-collisions

        Will return an ID if valid, otherwise an empty string.
        TODO: maybe its better to throw specific errors if validation fails
        TODO: is it better to include these experiment-related FNs in Xp-Class?
        TODO: Experiment-typehint for argument triggers circular import
        """
        raise NotImplementedError("TODO")

    def schedule_experiment(self, id_xp: str) -> bool:
        """Enqueue XP on testbed."""
        raise NotImplementedError("TODO")

    def get_experiment_status(self, id_xp: str) -> str:
        """Ask server about current state of XP.

        - after valid submission: disabled / deactivated
        - after scheduling: scheduled
        - before start-time: preparing
        - during run: active
        - after run: post-processing (collecting & assembling data)
        - finished: ready to download
        """
        raise NotImplementedError("TODO")

    def get_experiment_results(self, id_xp: str, path: Path) -> bool:
        """Download resulting files."""
        raise NotImplementedError("TODO")
