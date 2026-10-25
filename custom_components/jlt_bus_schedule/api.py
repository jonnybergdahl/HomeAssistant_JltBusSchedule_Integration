"""Client for the JLT (Jönköpings Länstrafik) departure board.

JLT has no public JSON API for departures, so this scrapes the HTML fragment
used by the departure board on jlt.se.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
import re
from zoneinfo import ZoneInfo

import aiohttp
from bs4 import BeautifulSoup

API_URL = "https://www.jlt.se/api/StopAreaApi/GetClosestDepartures"
USER_AGENT = "HomeAssistant-JltBusSchedule/1.0 (+https://www.home-assistant.io)"

# Departure times on jlt.se are always Swedish local time
JLT_TIMEZONE = ZoneInfo("Europe/Stockholm")

_TIME_RE = re.compile(r"(\d{1,2}):(\d{2})")
_DEPARTED_TEXT = "Har avgått"


class JltError(Exception):
    """Base error for the JLT client."""


class JltConnectionError(JltError):
    """Error communicating with jlt.se."""


@dataclass(frozen=True, slots=True)
class Departure:
    """A single upcoming departure."""

    line: str
    destination: str
    direction: str
    departure: datetime
    time_to_departure: str

    @property
    def departure_time(self) -> str:
        """Return the departure time formatted as HH:MM."""
        return self.departure.strftime("%H:%M")


def _clean(text: str) -> str:
    """Collapse all whitespace runs into single spaces."""
    return " ".join(text.split())


def parse_departures(html: str, now: datetime) -> list[Departure]:
    """Parse the departure board HTML fragment."""
    soup = BeautifulSoup(html, "html.parser")
    departures: list[Departure] = []

    for suggestion in soup.select("div.travel-suggestion"):
        direction_el = suggestion.select_one("div.direction")
        line_el = suggestion.select_one("div.line-info span")
        time_el = suggestion.select_one("p")
        if not direction_el or not line_el or not time_el:
            continue

        # Direction is shown as "mot <destination>"
        direction = _clean(direction_el.get_text(" ", strip=True))
        destination = direction[4:] if direction.lower().startswith("mot ") else direction

        # Time is shown as "12:34 (Avgår om 5 min)" or "Har avgått"
        raw = _clean(time_el.get_text(" ", strip=True))
        if _DEPARTED_TEXT in raw:
            continue
        match = _TIME_RE.match(raw)
        if not match:
            continue

        departure = now.replace(
            hour=int(match.group(1)),
            minute=int(match.group(2)),
            second=0,
            microsecond=0,
        )
        # Departures after midnight belong to the next day
        if departure < now - timedelta(hours=1):
            departure += timedelta(days=1)

        departures.append(
            Departure(
                line=line_el.get_text(strip=True),
                destination=destination,
                direction=direction,
                departure=departure,
                time_to_departure=raw[match.end() :].strip(" ()"),
            )
        )

    return departures


class JltApiClient:
    """Fetch departures from jlt.se."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Initialize the client."""
        self._session = session

    async def async_get_departures(
        self, stop_id: int, take: int, timeout: float = 10
    ) -> list[Departure]:
        """Return upcoming departures for all lines at a stop."""
        try:
            async with asyncio.timeout(timeout):
                response = await self._session.get(
                    API_URL,
                    params={"fromId": stop_id, "take": take},
                    headers={"User-Agent": USER_AGENT},
                )
                response.raise_for_status()
                html = await response.text()
        except (TimeoutError, aiohttp.ClientError) as err:
            raise JltConnectionError(
                f"Error fetching departures for stop {stop_id}: {err}"
            ) from err

        return parse_departures(html, datetime.now(JLT_TIMEZONE))
