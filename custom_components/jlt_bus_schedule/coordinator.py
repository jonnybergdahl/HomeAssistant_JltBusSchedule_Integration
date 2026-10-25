"""Data update coordinator for the JLT Bus Schedule integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from jlt_bus_schedule import Departure, JltApiClient, JltError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_DESTINATION,
    CONF_LINE,
    CONF_NUMBER_OF_DEPARTURES,
    CONF_SCAN_INTERVAL,
    CONF_STOP_ID,
    CONF_TOO_LATE_THRESHOLD,
    DEFAULT_NUMBER_OF_DEPARTURES,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TOO_LATE_THRESHOLD,
    DOMAIN,
    FETCH_COUNT,
)

_LOGGER = logging.getLogger(__name__)

type JltBusScheduleConfigEntry = ConfigEntry[JltBusScheduleCoordinator]


class JltBusScheduleCoordinator(DataUpdateCoordinator[list[Departure]]):
    """Fetch upcoming departures for one line and destination at a stop."""

    config_entry: JltBusScheduleConfigEntry

    def __init__(self, hass: HomeAssistant, entry: JltBusScheduleConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{entry.data[CONF_STOP_ID]}",
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )
        self.client = JltApiClient(async_get_clientsession(hass))
        self.stop_id: int = entry.data[CONF_STOP_ID]
        self.line: str = entry.data[CONF_LINE]
        self.destination: str = entry.data[CONF_DESTINATION]
        self.number_of_departures: int = entry.options.get(
            CONF_NUMBER_OF_DEPARTURES, DEFAULT_NUMBER_OF_DEPARTURES
        )
        self.too_late_threshold = timedelta(
            minutes=entry.options.get(
                CONF_TOO_LATE_THRESHOLD, DEFAULT_TOO_LATE_THRESHOLD
            )
        )

    async def _async_update_data(self) -> list[Departure]:
        """Fetch and filter departures."""
        try:
            departures = await self.client.async_get_departures(
                self.stop_id, FETCH_COUNT
            )
        except JltError as err:
            raise UpdateFailed(str(err)) from err

        return [
            departure
            for departure in departures
            if departure.line == self.line and self.destination in departure.direction
        ][: self.number_of_departures]
