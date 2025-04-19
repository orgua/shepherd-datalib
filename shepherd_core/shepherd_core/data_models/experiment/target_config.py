"""Configuration related to Target Nodes (DuT)."""

from typing import Annotated
from typing import Optional

from pydantic import Field
from pydantic import model_validator
from typing_extensions import Self

from ..base.content import IdInt
from ..base.shepherd import ShpModel
from ..content.energy_environment import EnergyEnvironment
from ..content.firmware import Firmware
from ..content.virtual_source import VirtualSourceConfig
from ..testbed.target import IdInt16
from ..testbed.target import Target
from .observer_features import GpioActuation
from .observer_features import GpioTracing
from .observer_features import PowerTracing


class TargetConfig(ShpModel, title="Target Config"):
    """Configuration related to Target Nodes (DuT)."""

    target_IDs: Annotated[list[IdInt], Field(min_length=1, max_length=128)]
    custom_IDs: Optional[Annotated[list[IdInt16], Field(min_length=1, max_length=128)]] = None
    # ⤷ will replace 'const uint16_t SHEPHERD_NODE_ID' in firmware
    #   if no custom ID is provided, the original ID of target is used

    energy_env: EnergyEnvironment  # alias: input
    virtual_source: VirtualSourceConfig = VirtualSourceConfig(name="neutral")
    target_delays: Optional[
        Annotated[list[Annotated[int, Field(ge=0)]], Field(min_length=1, max_length=128)]
    ] = None
    # ⤷ individual starting times -> allows to use the same environment
    # TODO: delays not used ATM

    firmware1: Firmware
    firmware2: Optional[Firmware] = None

    power_tracing: Optional[PowerTracing] = None
    gpio_tracing: Optional[GpioTracing] = None
    gpio_actuation: Optional[GpioActuation] = None

    @model_validator(mode="after")
    def post_validation(self) -> Self:
        if not self.energy_env.valid:
            msg = f"EnergyEnv '{self.energy_env.name}' for target must be valid"
            raise ValueError(msg)
        for _id in self.target_IDs:
            target = Target(id=_id)
            for mcu_num in [1, 2]:
                val_fw = getattr(self, f"firmware{mcu_num}")
                has_fw = val_fw is not None
                tgt_mcu = target[f"mcu{mcu_num}"]
                has_mcu = tgt_mcu is not None
                if not has_fw and has_mcu:
                    fw_def = Firmware(name=tgt_mcu.fw_name_default)
                    # ⤷ this will raise if default is faulty
                    if tgt_mcu.id != fw_def.mcu.id:
                        msg = (
                            f"Default-Firmware for MCU{mcu_num} of Target-ID '{target.id}' "
                            f"(={fw_def.mcu.name}) "
                            f"is incompatible (={tgt_mcu.name})"
                        )
                        raise ValueError(msg)
                if has_fw and has_mcu and val_fw.mcu.id != tgt_mcu.id:
                    msg = (
                        f"Firmware{mcu_num} for MCU of Target-ID '{target.id}' "
                        f"(={val_fw.mcu.name}) "
                        f"is incompatible (={tgt_mcu.name})"
                    )
                    raise ValueError(msg)

        c_ids = self.custom_IDs
        t_ids = self.target_IDs
        if c_ids is not None and (len(set(c_ids)) < len(set(t_ids))):
            msg = f"Provided custom IDs {c_ids} not enough to cover target range {t_ids}"
            raise ValueError(msg)
        # TODO: if custom ids present, firmware must be ELF
        return self

    def get_custom_id(self, target_id: int) -> Optional[int]:
        if self.custom_IDs is not None and target_id in self.target_IDs:
            return self.custom_IDs[self.target_IDs.index(target_id)]
        return None
