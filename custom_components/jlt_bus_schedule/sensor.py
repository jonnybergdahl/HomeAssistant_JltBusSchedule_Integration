"""Sensor platform for the JLT Bus Schedule integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
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
    """Set up sensors for each upcoming departure."""
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = []
    for index in range(1, coordinator.number_of_departures + 1):
        entities.extend(
            (
                JltDepartureSensor(coordinator, index),
                JltDepartureTimeSensor(coordinator, index),
                JltTimeToDepartureSensor(coordinator, index),
            )
        )
    async_add_entities(entities)


class JltDepartureSensor(JltBusScheduleEntity, SensorEntity):
    """Departure time, with all details as attributes."""

    def __init__(self, coordinator: JltBusScheduleCoordinator, index: int) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, Platform.SENSOR, "departure", "", index)

    @property
    def native_value(self) -> str | None:
        """Return the departure time as HH:MM."""
        departure = self.departure
        return departure.departure_time if departure else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return details about the departure."""
        if (departure := self.departure) is None:
            return None
        now = dt_util.now()
        return {
            "line_number": departure.line,
            "direction": departure.direction,
            "departure": departure.departure.isoformat(),
            "time_to_departure": departure.time_to_departure,
            "minutes_to_departure": max(
                0, int((departure.departure - now).total_seconds() // 60)
            ),
            "too_late": now > departure.departure - self.coordinator.too_late_threshold,
        }


class JltDepartureTimeSensor(JltBusScheduleEntity, SensorEntity):
    """Departure time only, without attributes.

    Useful as an automation trigger, as it only changes when the departure
    time changes.
    """

    def __init__(self, coordinator: JltBusScheduleCoordinator, index: int) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator, Platform.SENSOR, "departure_time", "_departure", index
        )

    @property
    def native_value(self) -> str | None:
        """Return the departure time as HH:MM."""
        departure = self.departure
        return departure.departure_time if departure else None


class JltTimeToDepartureSensor(JltBusScheduleEntity, SensorEntity):
    """Time to departure, as text from JLT."""

    def __init__(self, coordinator: JltBusScheduleCoordinator, index: int) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator,
            Platform.SENSOR,
            "time_to_departure",
            "_time_to_departure",
            index,
        )

    @property
    def native_value(self) -> str | None:
        """Return the time to departure, e.g. "Avgår om 5 min"."""
        departure = self.departure
        return departure.time_to_departure if departure else None
