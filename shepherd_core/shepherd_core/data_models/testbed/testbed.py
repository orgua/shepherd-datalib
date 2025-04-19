"""meta-data representation of a testbed-component (physical object)."""

from datetime import timedelta
from pathlib import Path
from typing import Annotated
from typing import Optional

from pydantic import Field
from pydantic import HttpUrl
from pydantic import model_validator
from typing_extensions import Self

from ... import logger
from ...testbed_client import tb_client
from ..base.content import IdInt
from ..base.content import NameStr
from ..base.content import SafeStr
from ..base.shepherd import ShpModel
from .observer import Observer


class Testbed(ShpModel):
    """meta-data representation of a testbed-component (physical object)."""

    id: IdInt
    name: NameStr
    description: SafeStr
    comment: Optional[SafeStr] = None

    url: Optional[HttpUrl] = None

    observers: Annotated[list[Observer], Field(min_length=1, max_length=128)]

    shared_storage: bool = True
    data_on_server: Path
    data_on_observer: Path
    # ⤷ storage layout: root_path/content_type/group/owner/[object]

    prep_duration: timedelta = timedelta(minutes=5)
    # TODO: one BBone is currently time-keeper

    @model_validator(mode="before")
    @classmethod
    def query_database(cls, values: dict) -> dict:
        # allow instantiating an empty Testbed
        #   -> query the first (and only) entry of client
        if len(values) == 0:
            ids = tb_client.query_ids(cls.__name__)
            if len(ids) > 1:
                logger.warning("More than one testbed defined?!?")
            values = {"id": ids[0]}

        values, _ = tb_client.try_completing_model(cls.__name__, values)
        return values

    @model_validator(mode="after")
    def post_validation(self) -> Self:
        observers = []
        ips = []
        macs = []
        capes = []
        targets = []
        eth_ports = []
        for _obs in self.observers:
            observers.append(_obs.id)
            ips.append(_obs.ip)
            macs.append(_obs.mac)
            if _obs.cape is not None:
                capes.append(_obs.cape)
            if _obs.target_a is not None:
                targets.append(_obs.target_a)
            if _obs.target_b is not None:
                targets.append(_obs.target_b)
            eth_ports.append(_obs.eth_port)
        if len(observers) > len(set(observers)):
            raise ValueError("Observers used more than once in Testbed")
        if len(ips) > len(set(ips)):
            raise ValueError("Observer-IP used more than once in Testbed")
        if len(macs) > len(set(macs)):
            raise ValueError("Observers-MAC-Address used more than once in Testbed")
        if len(capes) > len(set(capes)):
            raise ValueError("Cape used more than once in Testbed")
        if len(targets) > len(set(targets)):
            raise ValueError("Target used more than once in Testbed")
        if len(eth_ports) > len(set(eth_ports)):
            raise ValueError("Observers-Ethernet-Port used more than once in Testbed")
        if self.prep_duration.total_seconds() < 0:
            raise ValueError("Task-Duration can't be negative.")
        if not self.shared_storage:
            raise ValueError("Only shared-storage-option is implemented")
        return self

    def get_observer(self, target_id: int) -> Observer:
        for _observer in self.observers:
            if not _observer.active or not _observer.cape.active:
                # skip decommissioned setups
                continue
            if _observer.has_target(target_id):
                return _observer
        msg = f"Target-ID {target_id} was not found in Testbed '{self.name}'"
        raise ValueError(msg)
