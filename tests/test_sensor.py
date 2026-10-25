"""Tests for the JLT Bus Schedule sensors and binary sensors."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from jlt_bus_schedule import JltConnectionError
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from .conftest import DESTINATION, NOW, make_departure

PREFIX = "jlt_bus_1_north_departure"


@pytest.fixture(autouse=True)
def freeze_now(freezer: FrozenDateTimeFactory) -> None:
    """Freeze time at NOW."""
    freezer.move_to(NOW)


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set up the config entry."""
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_departures")
async def test_departure_sensors(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the entities of the first departure."""
    await _setup(hass, mock_config_entry)

    state = hass.states.get(f"sensor.{PREFIX}_1")
    assert state.state == "11:45"
    assert state.name == "JLT bus 1 north Departure 1"
    assert state.attributes["line_number"] == "1"
    assert state.attributes["direction"] == f"mot {DESTINATION}"
    assert state.attributes["departure"] == (NOW + timedelta(minutes=5)).isoformat()
    assert state.attributes["time_to_departure"] == "Avgår om 5 min"
    assert state.attributes["minutes_to_departure"] == 5
    assert state.attributes["too_late"] is True

    state = hass.states.get(f"sensor.{PREFIX}_1_departure")
    assert state.state == "11:45"
    assert state.name == "JLT bus 1 north Departure 1 time"
    assert "line_number" not in state.attributes

    state = hass.states.get(f"sensor.{PREFIX}_1_time_to_departure")
    assert state.state == "Avgår om 5 min"

    state = hass.states.get(f"binary_sensor.{PREFIX}_1_too_late")
    assert state.state == STATE_ON
    assert state.name == "JLT bus 1 north Departure 1 too late"


@pytest.mark.usefixtures("mock_departures")
async def test_filters_line_and_destination(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that only the configured line and destination are used, in order."""
    await _setup(hass, mock_config_entry)

    # 11:46 Råslätt and 12:00 line 28 are skipped, 12:25 is beyond the 3 departures
    assert [
        hass.states.get(f"sensor.{PREFIX}_{index}").state for index in (1, 2, 3)
    ] == ["11:45", "11:55", "12:10"]
    assert hass.states.get(f"sensor.{PREFIX}_4") is None


async def test_too_late_threshold(
    hass: HomeAssistant,
    mock_departures: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the too late binary sensor around the threshold."""
    # Threshold is 8 minutes
    mock_departures.return_value = [
        make_departure(7),
        make_departure(8),
        make_departure(9),
    ]
    await _setup(hass, mock_config_entry)

    assert [
        hass.states.get(f"binary_sensor.{PREFIX}_{index}_too_late").state
        for index in (1, 2, 3)
    ] == [STATE_ON, STATE_OFF, STATE_OFF]
    assert [
        hass.states.get(f"sensor.{PREFIX}_{index}").attributes["too_late"]
        for index in (1, 2, 3)
    ] == [True, False, False]


async def test_fewer_departures_than_configured(
    hass: HomeAssistant,
    mock_departures: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that entities without a departure are unknown."""
    mock_departures.return_value = [make_departure(15)]
    await _setup(hass, mock_config_entry)

    assert hass.states.get(f"sensor.{PREFIX}_1").state == "11:55"
    for entity_id in (
        f"sensor.{PREFIX}_2",
        f"sensor.{PREFIX}_2_departure",
        f"sensor.{PREFIX}_2_time_to_departure",
        f"binary_sensor.{PREFIX}_2_too_late",
    ):
        assert hass.states.get(entity_id).state == STATE_UNKNOWN
    assert "line_number" not in hass.states.get(f"sensor.{PREFIX}_2").attributes


async def test_update_and_unavailable(
    hass: HomeAssistant,
    mock_departures: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that states follow updates, and go unavailable on errors."""
    await _setup(hass, mock_config_entry)
    assert hass.states.get(f"sensor.{PREFIX}_1").state == "11:45"

    # The first bus has left
    mock_departures.return_value = mock_departures.return_value[1:]
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(f"sensor.{PREFIX}_1").state == "11:55"

    mock_departures.side_effect = JltConnectionError
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(f"sensor.{PREFIX}_1").state == STATE_UNAVAILABLE
    assert (
        hass.states.get(f"binary_sensor.{PREFIX}_1_too_late").state
        == STATE_UNAVAILABLE
    )

    mock_departures.side_effect = None
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(f"sensor.{PREFIX}_1").state == "11:55"
