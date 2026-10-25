"""Binary sensor platform for the JLT Bus Schedule integration."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import JltBusScheduleConfigEntry, JltBusScheduleCoordinator
from .entity import JltBusScheduleEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: JltBusScheduleConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a "too late" binary sensor for each upcoming departure."""
    coordinator = entry.runtime_data
    async_add_entities(
        JltTooLateBinarySensor(coordinator, index)
        for index in range(1, coordinator.number_of_departures + 1)
    )


class JltTooLateBinarySensor(JltBusScheduleEntity, BinarySensorEntity):
    """On when there is not enough time left to reach the departure."""

    def __init__(self, coordinator: JltBusScheduleCoordinator, index: int) -> None:
        """Initialize the binary sensor."""
        super().__init__(
            coordinator, Platform.BINARY_SENSOR, "too_late", "_too_late", index
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if now is later than departure minus the threshold."""
        if (departure := self.departure) is None:
            return None
        return (
            dt_util.now() > departure.departure - self.coordinator.too_late_threshold
        )
