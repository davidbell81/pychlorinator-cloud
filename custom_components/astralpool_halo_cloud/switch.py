"""Switch platform for the AstralPool Halo Cloud integration.

Provides on/off control for individual equipment timer slots.
"""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import HaloCloudCoordinator
from .entity import HaloCloudEntity


@dataclass
class _SlotDesc:
    key: str
    name: str


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AstralPool Halo Cloud switch entities."""
    coordinator: HaloCloudCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        HaloTimerSlotSwitch(coordinator, slot_index)
        for slot_index in range(4)
    )


class HaloTimerSlotSwitch(HaloCloudEntity, SwitchEntity):
    """Switch to enable or disable a single equipment timer slot."""

    _attr_icon = "mdi:timer-play-outline"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: HaloCloudCoordinator, slot_index: int) -> None:
        self._slot_index = slot_index
        desc = _SlotDesc(
            key=f"timer_slot_{slot_index}_active",
            name=f"Timer Slot {slot_index + 1} Active",
        )
        super().__init__(coordinator, desc)

    @property
    def available(self) -> bool:
        return (
            super().available
            and self.coordinator.client.data.connected
            and self._slot_index in self.coordinator.client.data.timer_configs
        )

    @property
    def is_on(self) -> bool | None:
        data = self.coordinator.data
        if data is None:
            return None
        config = data.timer_configs.get(self._slot_index)
        return bool(config.get("active")) if config is not None else None

    async def async_turn_on(self, **kwargs: object) -> None:
        await self._set_active(True)

    async def async_turn_off(self, **kwargs: object) -> None:
        await self._set_active(False)

    async def _set_active(self, enabled: bool) -> None:
        client = self.coordinator.client
        if not client.data.connected:
            raise HomeAssistantError("Chlorinator cloud is not connected")
        await client.write_timer_slot(self._slot_index, enabled=enabled)
        self.coordinator.async_set_updated_data(client.data)
