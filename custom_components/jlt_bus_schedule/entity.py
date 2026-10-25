"""Base entity for the JLT Bus Schedule integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .api import Departure
from .const import CONF_DIRECTION, CONF_STOP_NAME, DOMAIN, TRAVEL_PLANNER_URL
from .coordinator import JltBusScheduleCoordinator


class JltBusScheduleEntity(CoordinatorEntity[JltBusScheduleCoordinator]):
    """Entity representing one value of the n:th upcoming departure."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: JltBusScheduleCoordinator,
        platform: str,
        key: str,
        entity_id_suffix: str,
        index: int,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        direction = entry.data[CONF_DIRECTION]
        device_name = f"JLT bus {coordinator.line} {direction}"

        self._index = index
        self._attr_unique_id = f"{entry.entry_id}_{index}_{key}"
        self._attr_translation_key = key
        self._attr_translation_placeholders = {"index": str(index)}
        # Use the same entity IDs as the original AppDaemon app, independent of
        # the language Home Assistant is configured with
        self.entity_id = (
            f"{platform}.{slugify(device_name)}_departure_{index}{entity_id_suffix}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=device_name,
            manufacturer="Jönköpings Länstrafik",
            model=f"{entry.data.get(CONF_STOP_NAME) or coordinator.stop_id}, "
            f"line {coordinator.line} mot {coordinator.destination}",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=TRAVEL_PLANNER_URL,
        )

    @property
    def departure(self) -> Departure | None:
        """Return the departure this entity represents, if there is one."""
        if self.coordinator.data and len(self.coordinator.data) >= self._index:
            return self.coordinator.data[self._index - 1]
        return None
