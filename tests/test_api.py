"""Tests for the JLT client and departure board parser."""

from __future__ import annotations

from datetime import datetime, timedelta
import re

import aiohttp
import pytest
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.jlt_bus_schedule.api import (
    API_URL,
    JLT_TIMEZONE,
    STOP_SEARCH_URL,
    Stop,
    JltApiClient,
    JltConnectionError,
    parse_departures,
    parse_stops,
)
from custom_components.jlt_bus_schedule.const import FETCH_COUNT

from .conftest import DESTINATION, NOW, STOP_ID, load_fixture, make_html


def test_parse_recorded_response() -> None:
    """Test parsing a response recorded from jlt.se."""
    departures = parse_departures(load_fixture("departures_6001350.html"), NOW)

    assert len(departures) == 20
    first = departures[0]
    assert first.line == "1"
    assert first.destination == DESTINATION
    assert first.direction == f"mot {DESTINATION}"
    assert first.departure == datetime(2026, 10, 25, 11, 41, tzinfo=JLT_TIMEZONE)
    assert first.departure_time == "11:41"
    assert first.time_to_departure == "Avgår nu"
    assert departures[1].destination == "Råslätt"
    assert departures[1].time_to_departure == "Avgår om 1 min"
    assert {(d.line, d.destination) for d in departures} == {
        ("1", DESTINATION),
        ("1", "Råslätt"),
    }


def test_parse_collapses_whitespace() -> None:
    """Test that whitespace runs in the time to departure are collapsed."""
    departures = parse_departures(
        make_html(("1", "13:41 <span>(Avgår om 2h  0 min)</span>", "mot  Råslätt")),
        NOW,
    )

    assert departures[0].time_to_departure == "Avgår om 2h 0 min"
    assert departures[0].direction == "mot Råslätt"
    assert departures[0].destination == "Råslätt"


def test_parse_skips_departed_and_invalid() -> None:
    """Test that departed and malformed suggestions are skipped."""
    html = make_html(
        ("1", "Har avgått", "mot Råslätt"),
        ("1", "<span>(Inställd)</span>", "mot Råslätt"),
        ("1", "11:50 <span>(Avgår om 10 min)</span>", "mot Råslätt"),
    )
    html += '<div class="travel-suggestion"><p>11:55</p></div>'

    departures = parse_departures(html, NOW)

    assert [d.departure_time for d in departures] == ["11:50"]


def test_parse_without_mot_prefix() -> None:
    """Test a direction without the "mot" prefix."""
    departures = parse_departures(
        make_html(("28", "11:50 <span>(Avgår om 10 min)</span>", "Centrum")), NOW
    )

    assert departures[0].destination == "Centrum"
    assert departures[0].line == "28"


def test_parse_after_midnight() -> None:
    """Test that departures after midnight are placed on the next day."""
    now = datetime(2026, 10, 25, 23, 55, tzinfo=JLT_TIMEZONE)
    departures = parse_departures(
        make_html(
            ("1", "23:54 <span>(Avgår nu)</span>", "mot Råslätt"),
            ("1", "00:10 <span>(Avgår om 15 min)</span>", "mot Råslätt"),
        ),
        now,
    )

    assert departures[0].departure == datetime(
        2026, 10, 25, 23, 54, tzinfo=JLT_TIMEZONE
    )
    assert departures[1].departure == datetime(
        2026, 10, 26, 0, 10, tzinfo=JLT_TIMEZONE
    )


def test_parse_empty_response() -> None:
    """Test a stop without any upcoming departures."""
    assert parse_departures("", NOW) == []


async def test_client_fetches_departures(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test fetching departures."""
    aioclient_mock.get(API_URL, text=load_fixture("departures_6001350.html"))

    client = JltApiClient(async_get_clientsession(hass))
    departures = await client.async_get_departures(STOP_ID, FETCH_COUNT)

    assert len(departures) == 20
    assert aioclient_mock.call_count == 1
    url = aioclient_mock.mock_calls[0][1]
    assert url.query == {"fromId": str(STOP_ID), "take": str(FETCH_COUNT)}


@pytest.mark.parametrize(
    "kwargs",
    [
        {"status": 500},
        {"exc": aiohttp.ClientError},
        {"exc": TimeoutError},
    ],
)
async def test_client_errors(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, kwargs: dict
) -> None:
    """Test that HTTP and connection errors raise JltConnectionError."""
    aioclient_mock.get(API_URL, **kwargs)

    client = JltApiClient(async_get_clientsession(hass))
    with pytest.raises(JltConnectionError):
        await client.async_get_departures(STOP_ID, FETCH_COUNT)


@pytest.mark.live
@pytest.mark.usefixtures("live_network")
async def test_live_departures() -> None:
    """Test fetching and parsing departures from the live jlt.se site."""
    async with aiohttp.ClientSession() as session:
        # Check the raw response, so a markup change on jlt.se is detected even
        # if it makes the parser silently return nothing
        async with session.get(
            API_URL, params={"fromId": STOP_ID, "take": FETCH_COUNT}
        ) as response:
            assert response.status == 200
            html = await response.text()

        departures = await JltApiClient(session).async_get_departures(
            STOP_ID, FETCH_COUNT
        )

    assert html.count('class="travel-suggestion"') >= len(departures)
    if "travel-suggestion" in html and "Har avgått" not in html:
        assert departures, "jlt.se returned departures that could not be parsed"

    now = datetime.now(JLT_TIMEZONE)
    for departure in departures:
        assert departure.line
        assert departure.destination
        assert re.fullmatch(r"\d{2}:\d{2}", departure.departure_time)
        assert departure.time_to_departure.startswith("Avgår")
        assert now - timedelta(hours=1) <= departure.departure
        assert departure.departure <= now + timedelta(days=1)


def test_parse_recorded_stop_search() -> None:
    """Test parsing a stop search response recorded from the travel planner."""
    stops = parse_stops(load_fixture("stop_search_jonkoping.html"))

    assert len(stops) == 12
    assert stops[0] == Stop(id=6001242, name="Jönköping Juneporten")
    assert Stop(id=6001320, name="Jönköping Rådhusparken") in stops


def test_parse_stop_search_skips_invalid_and_duplicates() -> None:
    """Test that options without a numeric ID and duplicates are skipped."""
    html = """
        <li class="travel-option" data-id="Jönköping  Elmia|6001241|0">Elmia</li>
        <li class="travel-option" data-id="Storgatan 1, Jönköping|addr|1">x</li>
        <li class="travel-option" data-id="Utan id">x</li>
        <li class="travel-option">x</li>
        <li class="travel-option" data-id="Jönköping Elmia|6001241|0">Elmia</li>
    """

    assert parse_stops(html) == [Stop(id=6001241, name="Jönköping Elmia")]


async def test_client_searches_stops(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test searching for stops."""
    aioclient_mock.get(STOP_SEARCH_URL, text=load_fixture("stop_search_jonkoping.html"))

    client = JltApiClient(async_get_clientsession(hass))
    stops = await client.async_search_stops("Jönköping")

    assert len(stops) == 12
    url = aioclient_mock.mock_calls[0][1]
    assert url.query["letters"] == "Jönköping"
    assert url.query["optType"] == "0"


async def test_client_search_errors(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that errors when searching raise JltConnectionError."""
    aioclient_mock.get(STOP_SEARCH_URL, status=503)

    client = JltApiClient(async_get_clientsession(hass))
    with pytest.raises(JltConnectionError):
        await client.async_search_stops("Jönköping")


@pytest.mark.live
@pytest.mark.usefixtures("live_network")
async def test_live_stop_search() -> None:
    """Test searching for stops against the live JLT travel planner."""
    async with aiohttp.ClientSession() as session:
        client = JltApiClient(session)
        stops = await client.async_search_stops("Rådhusparken")
        # The stop IDs from the search must work with the departure board
        await client.async_get_departures(stops[0].id, 5)

    assert Stop(id=6001320, name="Jönköping Rådhusparken") in stops
