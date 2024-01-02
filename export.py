import asyncio
import logging
from math import log
import os
import signal
import sys
from functools import partial

import aiohttp
import dateutil.parser
import tibber
from influxdb import InfluxDBClient
from influxdb.exceptions import InfluxDBServerError, InfluxDBClientError

logging.basicConfig(level=logging.INFO)
logging.getLogger("gql.transport.websockets").setLevel(logging.WARNING)

log_level = os.getenv("LOG_LEVEL")

if log_level:
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level specified: {log_level}")
    logging.getLogger().setLevel(numeric_level)

    if numeric_level == logging.DEBUG:
        logging.getLogger("gql.transport.websockets").setLevel(logging.DEBUG)


def createInfluxPoint(data, homeId):
    timestamp = dateutil.parser.isoparse(data.get("timestamp"))
    timestamp_ns = int(timestamp.timestamp() * 1e9)  # influxdb timestamp in nanoseconds

    # first, convert all values to float if they are of type int according to the API schema
    # (sometimes the data is auto-converted to int by pyTibber)
    measurementData = map(
        lambda x: float(x) if isinstance(x, int) else x, data.values()
    )
    measurementData = dict(zip(data.keys(), measurementData))
    # not suitable as a field in InfluxDB due to high cardinality
    del measurementData["timestamp"]

    logging.debug("Creating influxDB data point %s", measurementData)

    return {
        "measurement": "tibber-measurement",
        "tags": {"home_id": homeId},
        "timestamp": timestamp_ns,
        "fields": measurementData,
    }


def writeMeasurement(influxClient: InfluxDBClient, homeId: str, measurement: dict):
    point = createInfluxPoint(measurement, homeId)
    influxClient.write_points([point])


def process_measurement(influxClient: InfluxDBClient, homeId: str, measurement: dict):
    data = measurement.get("data")
    if (
        data is None
        or data.get("liveMeasurement") is None
        or influxClient is None
        or homeId is None
    ):
        raise Exception("Invalid measurement received %s", measurement)

    try:
        writeMeasurement(influxClient, homeId, data.get("liveMeasurement"))
    except (InfluxDBServerError, InfluxDBClientError) as e:
        logging.exception("Exception caught while writing measurement to InfluxDB")


async def process_measurements(apiToken, influxClient):
    logging.info("Starting new connection...")
    try:
        async with aiohttp.ClientSession() as session:
            tibber_connection = tibber.Tibber(
                access_token=apiToken,
                websession=session,
                user_agent="tibber-export",
            )
            await tibber_connection.update_info()

        home = tibber_connection.get_homes()[0]

        callback = partial(process_measurement, influxClient, home.home_id)
        await home.rt_subscribe(callback)

        while True:
            await asyncio.sleep(15)
    except Exception as e:
        logging.exception("Exception caught while processing measurements")
    finally:
        logging.info("Closing connection...")
        if tibber_connection:
            tibber_connection.rt_disconnect()
            tibber_connection.close_connection()  # close the connection to the API

        logging.info("Sleeping 30 seconds...")
        await asyncio.sleep(30)


def sigterm_handler(signal, frame):
    logging.info("Received SIGTERM signal. Exiting gracefully...")
    loop = asyncio.get_running_loop()
    tasks = asyncio.all_tasks(loop=loop)

    for task in tasks:
        task.cancel()

    loop.stop()

    sys.exit(0)


if __name__ == "__main__":
    # Set the SIGTERM signal handler
    signal.signal(signal.SIGTERM, sigterm_handler)
    signal.signal(signal.SIGINT, sigterm_handler)

    influxHost = os.getenv("INFLUXDB_HOST")
    influxPort = os.getenv("INFLUXDB_PORT")
    influxDB = os.getenv("INFLUXDB_DB")
    influxUser = os.getenv("INFLUXDB_USER")
    influxPassword = os.getenv("INFLUXDB_PASSWORD")
    tibberToken = os.getenv("TIBBER_API_TOKEN")

    if None in (
        influxHost,
        influxPort,
        influxDB,
        influxUser,
        influxPassword,
        tibberToken,
    ):
        logging.error("Incomplete configuration")
        exit(1)
    else:
        logging.info("Retrieving power data from Tibber GraphQL endpoint")
        logging.info(
            "Sending telemetry to InfluxDB %s on port %s using TLS as user %s using database %s",
            influxHost,
            influxPort,
            influxUser,
            influxDB,
        )

    while True:
        try:
            influxClient = InfluxDBClient(
                host=influxHost,
                port=influxPort,
                username=influxUser,
                password=influxPassword,
                database=influxDB,
                ssl=True,
                verify_ssl=True,
            )

            loop = asyncio.get_event_loop()
            loop.run_until_complete(process_measurements(tibberToken, influxClient))
        except Exception as e:
            logging.exception("Exception caught while processing measurements in event loop")
        finally:
            influxClient.close()
