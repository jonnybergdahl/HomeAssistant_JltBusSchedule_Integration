"""Constants for the JLT Bus Schedule integration."""

from typing import Final

DOMAIN: Final = "jlt_bus_schedule"

CONF_STOP_ID: Final = "stop_id"
CONF_STOP_NAME: Final = "stop_name"
CONF_LINE: Final = "line"
CONF_DESTINATION: Final = "destination"
CONF_DIRECTION: Final = "direction"
CONF_TOO_LATE_THRESHOLD: Final = "too_late_threshold"
CONF_NUMBER_OF_DEPARTURES: Final = "number_of_departures"
CONF_SCAN_INTERVAL: Final = "scan_interval"

DEFAULT_TOO_LATE_THRESHOLD: Final = 8
DEFAULT_NUMBER_OF_DEPARTURES: Final = 6
DEFAULT_SCAN_INTERVAL: Final = 60

MAX_NUMBER_OF_DEPARTURES: Final = 20
MIN_SCAN_INTERVAL: Final = 30

# Number of departures to request from JLT. The API returns departures for all
# lines and directions at the stop, so fetch plenty and filter locally.
FETCH_COUNT: Final = 60
