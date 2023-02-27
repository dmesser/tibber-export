# pmeter
A silly Python app that reads a PMS7003 particulate sensor and writes the data into a InfluxSB

## Usage

This script expects a PMS7003 sensor to be connected via a serial port, GPIO or USB UART adapter and an InfluxDB database to save data.

The following environment variables are expected before running the script:

| Variable          | Description                                       | Required |
|-------------------|---------------------------------------------------|----------|
| INFLUXDB_HOST     | InfluxDB hostname                                 | yes      |
| INFLUXDB_PORT     | InfluxDB listen port                              | yes      |
| INFLUXDB_DB       | InfluxDB database name                            | yes      |
| INFLUXDB_USER     | InfluxDB user with write permissions              | yes      |
| INFLUXDB_PASSWORD | InfluxDB user password                            | yes      |
| DEVICE            | local serial device node (default `/dev/ttyUSB0`) | no       |

Measurements will be taken every 2 seconds, since the sensor might alter the reporting interval based on concentrate change (200-800 ms in fast mode or up to 2300 ms in stable mode).

## Prerequisites

 - Python3 (tested on 3.7.9)
 - Python3 PIP

## Installation

```sh
pip install -r requirements.txt
```

## Manual invocation

```sh
python3 pmeter.py
```

## Containerized invocation

Assuming credentials are externally stored, e.g. in a file `~/.secret`

```sh
INFLUXDB_HOST=example.com
INFLUXDB_PORT=8086
INFLUXDB_DB=pmeter
INFLUXDB_USER=username
INFLUXDB_PASSWORD=password
```

... and assuming the local serial port is `/dev/ttyUSB0`

```sh
podman run --detach --restart=always --privileged -h $(hostname) --device /dev/ttyUSB0 --env-file ~/.credentials dmesser/pmeter:latest
```

## Acknowledgements

- https://joshefin.xyz/air-quality-with-raspberrypi-pms7003-and-java/
- https://pypi.org/project/pms7003/