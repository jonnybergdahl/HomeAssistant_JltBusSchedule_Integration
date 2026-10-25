"""Config flow for the JLT Bus Schedule integration."""

from __future__ import annotations

import logging
from typing import Any

from jlt_bus_schedule import JltApiClient, JltError, Stop
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)
from homeassistant.util import slugify

from .const import (
    CONF_DESTINATION,
    CONF_DIRECTION,
    CONF_LINE,
    CONF_NUMBER_OF_DEPARTURES,
    CONF_SCAN_INTERVAL,
    CONF_STOP_ID,
    CONF_STOP_NAME,
    CONF_TOO_LATE_THRESHOLD,
    DEFAULT_NUMBER_OF_DEPARTURES,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TOO_LATE_THRESHOLD,
    DOMAIN,
    FETCH_COUNT,
    MAX_NUMBER_OF_DEPARTURES,
    MIN_SCAN_INTERVAL,
)
from .coordinator import JltBusScheduleConfigEntry

_LOGGER = logging.getLogger(__name__)

CONF_ROUTE = "route"
CONF_STOP = "stop"

STEP_USER_SCHEMA = vol.Schema({vol.Required(CONF_STOP): TextSelector()})

STEP_MANUAL_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_LINE): TextSelector(),
        vol.Required(CONF_DESTINATION): TextSelector(),
        vol.Required(CONF_DIRECTION): TextSelector(),
    }
)


class JltBusScheduleConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for JLT Bus Schedule."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._stop_id: int = 0
        self._stop_name: str | None = None
        self._stops: list[Stop] = []
        self._routes: list[tuple[str, str]] = []

    @property
    def _client(self) -> JltApiClient:
        """Return a JLT client."""
        return JltApiClient(async_get_clientsession(self.hass))

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the name or ID of the stop to monitor."""
        errors: dict[str, str] = {}
        if user_input is not None:
            query = user_input[CONF_STOP].strip()
            if query.isdigit():
                self._stop_id = int(query)
                self._stop_name = None
                if (error := await self._async_fetch_routes()) is None:
                    return await self._async_step_after_stop()
                errors["base"] = error
            elif query:
                try:
                    self._stops = await self._client.async_search_stops(query)
                except JltError:
                    errors["base"] = "cannot_connect"
                except Exception:
                    _LOGGER.exception("Unexpected error searching for stops")
                    errors["base"] = "unknown"
                else:
                    if self._stops:
                        return await self.async_step_stop()
                    errors[CONF_STOP] = "no_stops_found"
            else:
                errors[CONF_STOP] = "no_stops_found"

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_SCHEMA, user_input
            ),
            errors=errors,
        )

    async def async_step_stop(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick one of the stops matching the search."""
        errors: dict[str, str] = {}
        if user_input is not None:
            stop = next(
                stop for stop in self._stops if str(stop.id) == user_input[CONF_STOP]
            )
            self._stop_id = stop.id
            self._stop_name = stop.name
            if (error := await self._async_fetch_routes()) is None:
                return await self._async_step_after_stop()
            errors["base"] = error

        return self.async_show_form(
            step_id="stop",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_STOP): SelectSelector(
                            SelectSelectorConfig(
                                options=[
                                    SelectOptionDict(
                                        value=str(stop.id),
                                        label=f"{stop.name} ({stop.id})",
                                    )
                                    for stop in self._stops
                                ],
                                mode=SelectSelectorMode.LIST,
                            )
                        )
                    }
                ),
                user_input,
            ),
            errors=errors,
        )

    async def _async_fetch_routes(self) -> str | None:
        """Fetch the lines and destinations at the stop, return an error key."""
        try:
            departures = await self._client.async_get_departures(
                self._stop_id, FETCH_COUNT
            )
        except JltError:
            return "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected error fetching departures")
            return "unknown"

        self._routes = sorted(
            {(d.line, d.destination) for d in departures},
            key=lambda route: (
                (0, int(route[0])) if route[0].isdigit() else (1, 0),
                route,
            ),
        )
        return None

    async def _async_step_after_stop(self) -> ConfigFlowResult:
        """Continue with the route step, or manual entry without departures."""
        if not self._routes:
            return await self.async_step_manual()
        return await self.async_step_route()

    async def async_step_route(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick one of the lines and destinations at the stop."""
        if user_input is not None:
            line, destination = self._routes[int(user_input[CONF_ROUTE])]
            return await self._async_create(
                line, destination, user_input[CONF_DIRECTION]
            )

        return self.async_show_form(
            step_id="route",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ROUTE): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(
                                    value=str(index), label=f"{line} mot {destination}"
                                )
                                for index, (line, destination) in enumerate(
                                    self._routes
                                )
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Required(CONF_DIRECTION): TextSelector(),
                }
            ),
            description_placeholders={"stop": self._stop_title},
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Enter line and destination manually when no departures were found."""
        if user_input is not None:
            return await self._async_create(
                user_input[CONF_LINE].strip(),
                user_input[CONF_DESTINATION].strip(),
                user_input[CONF_DIRECTION],
            )

        return self.async_show_form(
            step_id="manual",
            data_schema=STEP_MANUAL_SCHEMA,
            description_placeholders={"stop": self._stop_title},
        )

    @property
    def _stop_title(self) -> str:
        """Return a human readable name of the stop."""
        return self._stop_name or str(self._stop_id)

    async def _async_create(
        self, line: str, destination: str, direction: str
    ) -> ConfigFlowResult:
        """Create the config entry."""
        await self.async_set_unique_id(f"{self._stop_id}_{line}_{destination}")
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=f"{self._stop_title}: {line} mot {destination}",
            data={
                CONF_STOP_ID: self._stop_id,
                CONF_STOP_NAME: self._stop_name,
                CONF_LINE: line,
                CONF_DESTINATION: destination,
                # Used in entity IDs, so keep it short and safe
                CONF_DIRECTION: slugify(direction) or "departures",
            },
            options={
                CONF_TOO_LATE_THRESHOLD: DEFAULT_TOO_LATE_THRESHOLD,
                CONF_NUMBER_OF_DEPARTURES: DEFAULT_NUMBER_OF_DEPARTURES,
                CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: JltBusScheduleConfigEntry,
    ) -> JltBusScheduleOptionsFlow:
        """Return the options flow."""
        return JltBusScheduleOptionsFlow()


class JltBusScheduleOptionsFlow(OptionsFlow):
    """Handle options for JLT Bus Schedule."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(
                data={key: int(value) for key, value in user_input.items()}
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_TOO_LATE_THRESHOLD): NumberSelector(
                    NumberSelectorConfig(
                        min=0,
                        max=120,
                        step=1,
                        unit_of_measurement="min",
                        mode=NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(CONF_NUMBER_OF_DEPARTURES): NumberSelector(
                    NumberSelectorConfig(
                        min=1,
                        max=MAX_NUMBER_OF_DEPARTURES,
                        step=1,
                        mode=NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(CONF_SCAN_INTERVAL): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_SCAN_INTERVAL,
                        max=3600,
                        step=1,
                        unit_of_measurement="s",
                        mode=NumberSelectorMode.BOX,
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                schema,
                {
                    CONF_TOO_LATE_THRESHOLD: DEFAULT_TOO_LATE_THRESHOLD,
                    CONF_NUMBER_OF_DEPARTURES: DEFAULT_NUMBER_OF_DEPARTURES,
                    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                    **self.config_entry.options,
                },
            ),
        )
