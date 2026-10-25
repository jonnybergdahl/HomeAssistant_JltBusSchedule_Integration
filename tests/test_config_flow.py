"""Tests for the JLT Bus Schedule config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.jlt_bus_schedule.api import JltConnectionError
from custom_components.jlt_bus_schedule.const import (
    CONF_DESTINATION,
    CONF_DIRECTION,
    CONF_LINE,
    CONF_NUMBER_OF_DEPARTURES,
    CONF_SCAN_INTERVAL,
    CONF_STOP_ID,
    CONF_STOP_NAME,
    CONF_TOO_LATE_THRESHOLD,
    DOMAIN,
)

from .conftest import DESTINATION, LINE, STOP_ID

DEFAULT_OPTIONS = {
    CONF_TOO_LATE_THRESHOLD: 8,
    CONF_NUMBER_OF_DEPARTURES: 6,
    CONF_SCAN_INTERVAL: 60,
}


async def _start_flow(hass: HomeAssistant, stop_id: str = str(STOP_ID), **extra):
    """Start a flow and submit the user step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_STOP_ID: stop_id, **extra}
    )


def _route_options(result) -> dict[str, str]:
    """Return the route selector options as label -> value."""
    selector = result["data_schema"].schema["route"]
    return {option["label"]: option["value"] for option in selector.config["options"]}


async def test_user_flow(hass: HomeAssistant, mock_departures: AsyncMock) -> None:
    """Test selecting a line and destination from the upcoming departures."""
    result = await _start_flow(hass, f" {STOP_ID} ", **{CONF_STOP_NAME: "Rådhusparken"})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "route"
    assert result["description_placeholders"] == {"stop": "Rådhusparken"}
    options = _route_options(result)
    # Sorted on line number, then destination
    assert list(options) == [
        f"1 mot {DESTINATION}",
        "1 mot Råslätt",
        f"28 mot {DESTINATION}",
    ]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"route": options[f"1 mot {DESTINATION}"], CONF_DIRECTION: "North"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Rådhusparken: 1 mot {DESTINATION}"
    assert result["result"].unique_id == f"{STOP_ID}_1_{DESTINATION}"
    assert result["data"] == {
        CONF_STOP_ID: STOP_ID,
        CONF_STOP_NAME: "Rådhusparken",
        CONF_LINE: "1",
        CONF_DESTINATION: DESTINATION,
        CONF_DIRECTION: "north",
    }
    assert result["options"] == DEFAULT_OPTIONS
    mock_departures.assert_awaited()


async def test_user_flow_without_stop_name(
    hass: HomeAssistant, mock_departures: AsyncMock
) -> None:
    """Test that the stop ID is used when no stop name is given."""
    result = await _start_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"route": "1", CONF_DIRECTION: "south"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"{STOP_ID}: 1 mot Råslätt"
    assert result["data"][CONF_STOP_NAME] is None


async def test_manual_flow(hass: HomeAssistant, mock_departures: AsyncMock) -> None:
    """Test entering line and destination when there are no departures."""
    mock_departures.return_value = []

    result = await _start_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_LINE: " 28 ", CONF_DESTINATION: " Centrum ", CONF_DIRECTION: "Väst"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_STOP_ID: STOP_ID,
        CONF_STOP_NAME: None,
        CONF_LINE: "28",
        CONF_DESTINATION: "Centrum",
        CONF_DIRECTION: "vast",
    }


@pytest.mark.parametrize("stop_id", ["abc", "60013a", ""])
async def test_invalid_stop_id(
    hass: HomeAssistant, mock_departures: AsyncMock, stop_id: str
) -> None:
    """Test that a non numeric stop ID is rejected."""
    result = await _start_flow(hass, stop_id)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_STOP_ID: "invalid_stop_id"}
    mock_departures.assert_not_awaited()


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [(JltConnectionError, "cannot_connect"), (ValueError, "unknown")],
)
async def test_fetch_errors(
    hass: HomeAssistant,
    mock_departures: AsyncMock,
    side_effect: type[Exception],
    error: str,
) -> None:
    """Test errors when fetching departures, and recovering from them."""
    return_value = mock_departures.return_value
    mock_departures.side_effect = side_effect

    result = await _start_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error}

    mock_departures.side_effect = None
    mock_departures.return_value = return_value
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_STOP_ID: str(STOP_ID)}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "route"


async def test_already_configured(
    hass: HomeAssistant,
    mock_departures: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the same stop, line and destination can't be added twice."""
    mock_config_entry.add_to_hass(hass)

    result = await _start_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"route": _route_options(result)[f"{LINE} mot {DESTINATION}"], CONF_DIRECTION: "x"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow(
    hass: HomeAssistant,
    mock_departures: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test changing the options reloads the entry with the new options."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_TOO_LATE_THRESHOLD: 10.0,
            CONF_NUMBER_OF_DEPARTURES: 2.0,
            CONF_SCAN_INTERVAL: 120.0,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options == {
        CONF_TOO_LATE_THRESHOLD: 10,
        CONF_NUMBER_OF_DEPARTURES: 2,
        CONF_SCAN_INTERVAL: 120,
    }
    coordinator = mock_config_entry.runtime_data
    assert coordinator.number_of_departures == 2
    assert coordinator.update_interval.total_seconds() == 120
    assert coordinator.too_late_threshold.total_seconds() == 600


@pytest.mark.live
@pytest.mark.usefixtures("live_network")
async def test_live_user_flow(hass: HomeAssistant) -> None:
    """Test the user step against the live jlt.se site."""
    result = await _start_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result.get("errors") in (None, {})
    # Route when there are upcoming departures, manual at night
    assert result["step_id"] in ("route", "manual")
    if result["step_id"] == "route":
        assert any(label.startswith("1 mot ") for label in _route_options(result))
