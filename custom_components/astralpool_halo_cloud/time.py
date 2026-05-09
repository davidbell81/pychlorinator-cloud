"""Time platform for the AstralPool Halo Cloud integration.

Provides start-time and stop-time controls for each equipment timer slot.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import HaloCloudCoordinator
from .entity import HaloCloudEntity


@dataclass
class _SlotTimeDesc:
    key: str
    name: str


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AstralPool Halo Cloud time entities."""
    coordinator: HaloCloudCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[HaloTimerSlotTime] = []
    for slot_index in range(4):
        slot_num = slot_index + 1
        entities.append(
            HaloTimerSlotTime(
                coordinator,
                slot_index=slot_index,
                is_start=True,
                key=f"timer_slot_{slot_index}_start_time",
                name=f"Timer Slot {slot_num} Start",
            )
        )
        entities.append(
            HaloTimerSlotTime(
                coordinator,
                slot_index=slot_index,
                is_start=False,
                key=f"timer_slot_{slot_index}_stop_time",
                name=f"Timer Slot {slot_num} Stop",
            )
        )
    async_add_entities(entities)


class HaloTimerSlotTime(HaloCloudEntity, TimeEntity):
    """Time entity controlling the start or stop time for a timer slot."""

    _attr_icon = "mdi:clock-outline"
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: HaloCloudCoordinator,
        *,
        slot_index: int,
        is_start: bool,
        key: str,
        name: str,
    ) -> None:
        self._slot_index = slot_index
        self._is_start = is_start
        super().__init__(coordinator, _SlotTimeDesc(key=key, name=name))

    @property
    def available(self) -> bool:
        return (
            super().available
            and self.coordinator.client.data.connected
            and self._slot_index in self.coordinator.client.data.timer_configs
        )

    @property
    def native_value(self) -> datetime.time | None:
        data = self.coordinator.data
        if data is None:
            return None
        config = data.timer_configs.get(self._slot_index)
        if config is None:
            return None
        if self._is_start:
            hour = config.get("start_hour")
            minute = config.get("start_minute")
        else:
            hour = config.get("stop_hour")
            minute = config.get("stop_minute")
        if hour is None or minute is None:
            return None
        try:
            return datetime.time(hour, minute)
        except ValueError:
            return None

    async def async_set_value(self, value: datetime.time) -> None:
        client = self.coordinator.client
        if not client.data.connected:
            raise HomeAssistantError("Chlorinator cloud is not connected")
        if self._is_start:
            await client.write_timer_slot(
                self._slot_index,
                start_hour=value.hour,
                start_minute=value.minute,
            )
        else:
            await client.write_timer_slot(
                self._slot_index,
                stop_hour=value.hour,
                stop_minute=value.minute,
            )
        self.coordinator.async_set_updated_data(client.data)
