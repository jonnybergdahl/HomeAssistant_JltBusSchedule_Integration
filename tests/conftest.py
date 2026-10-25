"""Fixtures for JLT Bus Schedule tests."""

from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timedelta
import socket
from unittest.mock import AsyncMock, patch

from jlt_bus_schedule import JLT_TIMEZONE, Departure, Stop
import pytest
import pytest_socket
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.plugins import _real_getaddrinfo

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

STOP_ID = 6001350
LINE = "1"
DESTINATION = "Huskvarna via Centrum-Elmia"

# Time used for tests with a frozen clock
NOW = datetime(2026, 10, 25, 11, 40, tzinfo=JLT_TIMEZONE)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable loading the integration from custom_components."""


@pytest.fixture
def live_network(
    monkeypatch: pytest.MonkeyPatch, disable_mock_zeroconf_resolver: None
) -> None:
    """Allow a test to access the internet.

    The Home Assistant test harness blocks sockets and DNS resolution, and
    replaces the DNS resolver of the Home Assistant aiohttp session. The
    restrictions are set up again before the next test.
    """
    pytest_socket._remove_restrictions()  # noqa: SLF001
    monkeypatch.setattr(socket, "getaddrinfo", _real_getaddrinfo)


def make_departure(
    minutes: int, line: str = LINE, destination: str = DESTINATION
) -> Departure:
    """Return a departure the given number of minutes after NOW."""
    return Departure(
        line=line,
        destination=destination,
        direction=f"mot {destination}",
        departure=NOW + timedelta(minutes=minutes),
        time_to_departure=f"Avgår om {minutes} min" if minutes else "Avgår nu",
    )


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a config entry for line 1 towards Huskvarna."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=f"Rådhusparken: {LINE} mot {DESTINATION}",
        unique_id=f"{STOP_ID}_{LINE}_{DESTINATION}",
        data={
            CONF_STOP_ID: STOP_ID,
            CONF_STOP_NAME: "Rådhusparken",
            CONF_LINE: LINE,
            CONF_DESTINATION: DESTINATION,
            CONF_DIRECTION: "north",
        },
        options={
            CONF_TOO_LATE_THRESHOLD: 8,
            CONF_NUMBER_OF_DEPARTURES: 3,
            CONF_SCAN_INTERVAL: 60,
        },
    )


@pytest.fixture
def mock_departures() -> Generator[AsyncMock]:
    """Patch the JLT client to return a fixed set of departures."""
    with patch(
        "jlt_bus_schedule.JltApiClient.async_get_departures",
        autospec=True,
    ) as mock:
        mock.return_value = [
            make_departure(5),
            make_departure(6, destination="Råslätt"),
            make_departure(15),
            make_departure(20, line="28"),
            make_departure(30),
            make_departure(45),
        ]
        yield mock


@pytest.fixture
def mock_stop_search() -> Generator[AsyncMock]:
    """Patch the JLT client to return a fixed set of stops."""
    with patch(
        "jlt_bus_schedule.JltApiClient.async_search_stops",
        autospec=True,
    ) as mock:
        mock.return_value = [
            Stop(id=STOP_ID, name="Jönköping Rådhusparken"),
            Stop(id=6001001, name="Jönköping Resecentrum"),
        ]
        yield mock
