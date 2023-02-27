# tibber-export
A silly Python app that reads power consumption data from Tibber's GraphQL API using [pyTibber](https://github.com/Danielhiversen/pyTibber) and writes it into a InfluxDB instance. Tibber ([tibber.com](https://tibber.com)) is an electricity provider with 15-minute accurate cost calculation based on electricity prices from the European Power Exchange. You should have a [Tibber Pulse](https://tibber.com/de/store/produkt/pulse-ir) to get accurate readings.

## Usage

This script expects you to have an API token that you can obtain from the [Tibber Developer Portal](https://developer.tibber.com/settings/access-token).

The following environment variables are expected before running the script:

| Variable            | Description                                       | Required |
|---------------------|---------------------------------------------------|----------|
| INFLUXDB_HOST       | InfluxDB hostname                                 | yes      |
| INFLUXDB_PORT       | InfluxDB listen port                              | yes      |
| INFLUXDB_DB         | InfluxDB database name                            | yes      |
| INFLUXDB_USER       | InfluxDB user with write permissions              | yes      |
| INFLUXDB_PASSWORD   | InfluxDB user password                            | yes      |
| TIBBER_API_ENDPOINT | usually https://api.tibber.com/v1-beta/gql        | yes      |
| TIBBER_API_TOKEN    | Tibber API token                                  | yes      |

Measurements will be taken every couple of seconds, depending on how fast the Tibber API delivers them. In the background this is accomplished using [pyTibber](https://github.com/Danielhiversen/pyTibber) which leverages a long-lived websocket connection to get near-realtime updates from your power consumption

## What is stored?

Here is an example response from Tibber that iss stored in InfluxDB:

```json
{
  "data": {
    "liveMeasurement": {
      "accumulatedConsumption": 7.1822,
      "accumulatedConsumptionLastHour": 0.2645,
      "accumulatedCost": 2.309316,
      "accumulatedProduction": 0,
      "accumulatedProductionLastHour": 0,
      "accumulatedReward": "None",
      "averagePower": 488.8,
      "currency": "EUR",
      "currentL1": "None",
      "currentL2": "None",
      "currentL3": "None",
      "lastMeterConsumption": 8238.9331,
      "lastMeterProduction": -1,
      "maxPower": 2540,
      "minPower": 302,
      "power": 356,
      "powerFactor": "None",
      "powerProduction": 0,
      "powerReactive": "None",
      "signalStrength": "None",
      "timestamp": "2023-02-12bT14:41:28.000+01:00",
      "voltagePhase1": "None",
      "voltagePhase2": "None",
      "voltagePhase3": "None",
      "estimatedHourConsumption": 0.374
    }
  }
}
```

See [here for a documentation](https://developer.tibber.com/docs/reference#livemeasurement) of these values.

## Prerequisites

 - Python3 (tested on 3.10.10)
 - Python3 PIP
 - [podman](https://podman.io/) (optional)

## Installation

```sh
pip install -r requirements.txt
```

## Manual invocation

```sh
python3 export.py
```

## Containerized invocation

Assuming credentials are externally stored, e.g. in a file `~/.secret`

```sh
INFLUXDB_HOST=example.com
INFLUXDB_PORT=8086
INFLUXDB_DB=tibber-export
INFLUXDB_USER=username
INFLUXDB_PASSWORD=password
TIBBER_API_ENDPOINT=https://api.tibber.com/v1-beta/gql
TIBBER_API_TOKEN=5K4MVS-OjfWhK_4yrjOlFe1F6kJXPVf7eQYggo8ebAE
```

```sh
podman run --detach --restart=always --env-file ~/.secret quay.io/dmesser/tibber-export:main
```

## Acknowledgements

- https://github.com/influxdata/influxdb-python
- https://pypi.org/project/pyTibber/