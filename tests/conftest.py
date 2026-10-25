"""Fixtures for JLT Bus Schedule tests."""

from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timedelta
from pathlib import Path
import socket
from unittest.mock import AsyncMock, patch

import pytest
import pytest_socket
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.plugins import _real_getaddrinfo

from custom_components.jlt_bus_schedule.api import JLT_TIMEZONE, Departure, Stop
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

FIXTURES = Path(__file__).parent / "fixtures"

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


def load_fixture(name: str) -> str:
    """Load a fixture file."""
    return (FIXTURES / name).read_text(encoding="utf-8")


def make_html(*suggestions: tuple[str, str, str]) -> str:
    """Build a departure board fragment from (line, time text, direction)."""
    return "\n".join(
        f"""
    <div class="travel-suggestion">
        <a class="info" href="/res-med-oss/linjer-hallplatser/linje/?id={line}">
            <p>
                {time_text}
            </p>
            <div class="destination">
                <div class="line-info-area">
                    <div class="icon-shape number"><div><span class="text">S</span></div></div>
                    <div class="icon-shape line-info"><span class="text">{line}</span></div>
                </div>
                <div class="direction">
                    {direction}
                </div>
            </div>
        </a>
    </div>"""
        for line, time_text, direction in suggestions
    )


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
        "custom_components.jlt_bus_schedule.api.JltApiClient.async_get_departures",
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
        "custom_components.jlt_bus_schedule.api.JltApiClient.async_search_stops",
        autospec=True,
    ) as mock:
        mock.return_value = [
            Stop(id=STOP_ID, name="Jönköping Rådhusparken"),
            Stop(id=6001001, name="Jönköping Resecentrum"),
        ]
        yield mock
