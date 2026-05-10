"""Switch platform for the AstralPool Halo Cloud integration.

Provides on/off control for individual equipment timer slots and per-slot heater enable.
"""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from pychlorinator_cloud.timers import ENABLES_HEATER

from .const import DOMAIN
from .coordinator import HaloCloudCoordinator
from .entity import HaloCloudEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AstralPool Halo Cloud switch entities."""
    coordinator: HaloCloudCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SwitchEntity] = []
    for slot_index in range(4):
        entities.append(HaloTimerSlotSwitch(coordinator, slot_index))
        entities.append(HaloTimerSlotHeaterSwitch(coordinator, slot_index))
    async_add_entities(entities)


class HaloTimerSlotSwitch(HaloCloudEntity, SwitchEntity):
    """Switch to enable or disable a single equipment timer slot."""

    _attr_icon = "mdi:timer-play-outline"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: HaloCloudCoordinator, slot_index: int) -> None:
        self._slot_index = slot_index
        desc = SwitchEntityDescription(
            key=f"timer_slot_{slot_index}_active",
            name=f"Timer Slot {slot_index + 1} Active",
        )
        super().__init__(coordinator, desc)

    @property
    def available(self) -> bool:
        return (
            super().available
            and self.coordinator.client.data.connected
            and self._slot_index in self.coordinator.client.data.equipment_timer_configs
        )

    @property
    def is_on(self) -> bool | None:
        data = self.coordinator.data
        if data is None:
            return None
        config = data.equipment_timer_configs.get(self._slot_index)
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


class HaloTimerSlotHeaterSwitch(HaloCloudEntity, SwitchEntity):
    """Switch to enable or disable the heater in a single equipment timer slot."""

    _attr_icon = "mdi:radiator"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: HaloCloudCoordinator, slot_index: int) -> None:
        self._slot_index = slot_index
        desc = SwitchEntityDescription(
            key=f"timer_slot_{slot_index}_heater",
            name=f"Timer Slot {slot_index + 1} Heater",
        )
        super().__init__(coordinator, desc)

    @property
    def available(self) -> bool:
        return (
            super().available
            and self.coordinator.client.data.connected
            and self._slot_index in self.coordinator.client.data.equipment_timer_configs
        )

    @property
    def is_on(self) -> bool | None:
        data = self.coordinator.data
        if data is None:
            return None
        config = data.equipment_timer_configs.get(self._slot_index)
        if config is None:
            return None
        return bool(config.get("enables", 0) & ENABLES_HEATER)

    async def async_turn_on(self, **kwargs: object) -> None:
        await self._set_heater(True)

    async def async_turn_off(self, **kwargs: object) -> None:
        await self._set_heater(False)

    async def _set_heater(self, enable: bool) -> None:
        client = self.coordinator.client
        if not client.data.connected:
            raise HomeAssistantError("Chlorinator cloud is not connected")
        existing = client.data.equipment_timer_configs.get(self._slot_index)
        if existing is None:
            raise HomeAssistantError(f"Timer slot {self._slot_index + 1} config not yet received")
        current_enables = existing.get("enables", 0)
        if enable:
            new_enables = current_enables | ENABLES_HEATER
        else:
            new_enables = current_enables & ~ENABLES_HEATER
        await client.write_timer_slot(self._slot_index, enables=new_enables)
        self.coordinator.async_set_updated_data(client.data)
