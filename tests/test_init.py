"""Tests for setting up and unloading JLT Bus Schedule."""

from __future__ import annotations

from unittest.mock import AsyncMock

from jlt_bus_schedule import JltConnectionError
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from custom_components.jlt_bus_schedule.const import DOMAIN, FETCH_COUNT

from .conftest import STOP_ID


async def test_setup_and_unload(
    hass: HomeAssistant,
    mock_departures: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setting up and unloading a config entry."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_departures.assert_awaited_once()
    assert mock_departures.await_args.args[1:] == (STOP_ID, FETCH_COUNT)

    devices = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert len(devices) == 1
    device = devices[0]
    assert device.identifiers == {(DOMAIN, mock_config_entry.entry_id)}
    assert device.name == "JLT bus 1 north"
    assert device.manufacturer == "Jönköpings Länstrafik"
    assert device.model == "Rådhusparken, line 1 mot Huskvarna via Centrum-Elmia"
    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    # 3 departures with 4 entities each
    assert len(entries) == 12
    assert all(entry.device_id == device.id for entry in entries)

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_retry_on_connection_error(
    hass: HomeAssistant,
    mock_departures: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that setup is retried when jlt.se can't be reached."""
    mock_departures.side_effect = JltConnectionError

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.live
@pytest.mark.usefixtures("live_network")
async def test_live_setup(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setting up a config entry against the live jlt.se site."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    state = hass.states.get("sensor.jlt_bus_1_north_departure_1")
    assert state is not None
    # Unknown when there are no upcoming departures, at night
    assert state.state == "unknown" or state.state[2] == ":"

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
