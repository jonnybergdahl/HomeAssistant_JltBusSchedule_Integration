# JLT Bus Schedule

A Home Assistant integration that publishes upcoming JLT (Jönköpings Länstrafik) bus departures as sensors.

It is a port of the AppDaemon app [Python_Appdaemon_JltBusSchedule](https://github.com/jonnybergdahl/Python_Appdaemon_JltBusSchedule)
to a native integration with UI configuration. It uses the same entity IDs, so existing dashboards and automations keep working
(see [Migrating from the AppDaemon app](#migrating-from-the-appdaemon-app)).

JLT has no public API for departures, so the integration scrapes
`https://www.jlt.se/api/StopAreaApi/GetClosestDepartures?fromId={stop_id}&take=60`, the HTML fragment used by the departure board on jlt.se.

## Installation

### HACS

Click the button to add this repository to HACS.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=jonnybergdahl&category=Integration&repository=HomeAssistant_JltBusSchedule_Integration)

Then download the integration and restart Home Assistant.

You can also do this manually:

1. In HACS, open the menu in the top right corner and select **Custom repositories**.
2. Add `https://github.com/jonnybergdahl/HomeAssistant_JltBusSchedule_Integration` with the type **Integration**.
3. Search for **JLT Bus Schedule**, download it and restart Home Assistant.

### Manual

Copy `custom_components/jlt_bus_schedule` to the `custom_components` folder in your Home Assistant configuration directory, and restart Home Assistant.

## Configuration

Click the button to start setting up the integration.

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=jlt_bus_schedule)

You can also go to **Settings → Devices & services → Add integration** and select **JLT Bus Schedule**.

1. **Stop ID**. Go to https://www.jlt.se/res-med-oss/linjer-hallplatser/ and search for the bus stop. Select it and
   look at the URL. The stop ID is the number at the end of the URL. You can also give the stop a name, which is only used in the entry title.
2. **Line and destination**. The integration fetches the upcoming departures from the stop and lets you pick a line and destination.
   If there are no upcoming departures (at night, for example), you enter the line and destination manually instead.
   The destination is the text after "mot" on jlt.se, for example `Huskvarna via Centrum-Elmia`.
3. **Direction alias**. A short name such as `north` or `west`, used in the entity IDs, so keep it short.

Add the integration once for each line and destination you want to follow.

### Options

Select **Configure** on the integration entry to change these:

| Option               | Default | Description                                                              |
|----------------------|---------|--------------------------------------------------------------------------|
| Too late threshold   | 8 min   | Minutes it takes to get to the bus stop. Used by the `too_late` entities. |
| Number of departures | 6       | Number of upcoming departures to create entities for.                    |
| Update interval      | 60 s    | How often to fetch departures from jlt.se.                               |

## Entities

Each entry creates a device named `JLT bus <line> <direction>` with these entities for each departure `n`
(1 up to the number of departures):

| Entity ID                                                               | State                    | Description                                                     |
|-------------------------------------------------------------------------|--------------------------|-----------------------------------------------------------------|
| `sensor.jlt_bus_<line>_<direction>_departure_<n>`                       | `HH:MM`                  | Departure time, with all details as attributes (see below)      |
| `sensor.jlt_bus_<line>_<direction>_departure_<n>_departure`             | `HH:MM`                  | Departure time, without attributes                              |
| `sensor.jlt_bus_<line>_<direction>_departure_<n>_time_to_departure`     | for example `Avgår om 5 min` | Time to departure, as text from jlt.se                      |
| `binary_sensor.jlt_bus_<line>_<direction>_departure_<n>_too_late`       | `on` / `off`             | On when now is later than departure time minus the threshold    |

When there are fewer upcoming departures than configured, the remaining entities are `unknown`.

Attributes of `sensor.jlt_bus_<line>_<direction>_departure_<n>`:

| Attribute              | Example                              |
|------------------------|--------------------------------------|
| `line_number`          | `1`                                  |
| `direction`            | `mot Huskvarna via Centrum-Elmia`    |
| `departure`            | `2026-10-25T11:56:00+01:00`          |
| `time_to_departure`    | `Avgår om 15 min`                    |
| `minutes_to_departure` | `15`                                 |
| `too_late`             | `false`                              |

> Note: The first sensor is the normal one to use, as it contains all data as attributes.
> If you use it as a trigger for an automation however, it will trigger on attribute changes as well, and
> `time_to_departure` changes every minute. Use the `..._departure` sensor as a trigger instead.

## Dashboard

You can use the markdown card to display the schedule.

```jinja
# Linje 1
## {{ states('sensor.jlt_bus_1_north_departure_1') }} ({{ states('sensor.jlt_bus_1_north_departure_1_time_to_departure') }})

{{ states('sensor.jlt_bus_1_north_departure_2') }} - ({{ states('sensor.jlt_bus_1_north_departure_2_time_to_departure') }})
{{ states('sensor.jlt_bus_1_north_departure_3') }} - ({{ states('sensor.jlt_bus_1_north_departure_3_time_to_departure') }})
{{ states('sensor.jlt_bus_1_north_departure_4') }} - ({{ states('sensor.jlt_bus_1_north_departure_4_time_to_departure') }})
{{ states('sensor.jlt_bus_1_north_departure_5') }} - ({{ states('sensor.jlt_bus_1_north_departure_5_time_to_departure') }})
```

For an OpenEPaperLink example, see the [AppDaemon app README](https://github.com/jonnybergdahl/Python_Appdaemon_JltBusSchedule#openepaperlink).
It works unchanged with this integration.

## Migrating from the AppDaemon app

1. Remove or disable the AppDaemon app, and restart Home Assistant so the states it created are gone.
2. Add the integration once for each entry in `TARGETS`, using the same stop ID, destination and direction alias.
3. Set the options to match `TOO_LATE_TRESHOLD` and `NUMBER_OF_DEPARTURES`.

The entity IDs are the same as before, with one difference: `..._too_late` is now a binary sensor,
`binary_sensor.jlt_bus_<line>_<direction>_departure_<n>_too_late` with the state `on`/`off`, instead of a sensor with
the state `True`/`False`. Update any templates and automations that use it.

Unlike the AppDaemon app, departures are filtered on line number as well as destination.

## Development

The tests use [pytest-homeassistant-custom-component](https://github.com/MatthewFlamm/pytest-homeassistant-custom-component),
which requires the same Python version as the latest Home Assistant release.

```shell
python -m venv venv
venv/bin/pip install -r requirements_test.txt
venv/bin/pytest
```

Tests marked `live` call the live jlt.se site. Skip them with `pytest -m "not live"`.

The brand images in `custom_components/jlt_bus_schedule/brand` are shown by Home Assistant 2026.3 and later.
