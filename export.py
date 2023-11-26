import asyncio
import os
import signal
import sys
from functools import partial
import time

import aiohttp
import dateutil.parser
import tibber
from influxdb import InfluxDBClient

last_measurement_time = 0

def createInfluxPoint(data, homeId):
    timestamp = dateutil.parser.isoparse(data.get("timestamp"))
    timestamp_ns = int(timestamp.timestamp() * 1e9)  # influxdb timestamp in nanoseconds

    # first, convert all values to float if they are of type int according to the API schema
    # (sometimes the data is auto-converted to int by pyTibber)
    measurementData = map(lambda x: float(x) if isinstance(x, int) else x, data.values())
    measurementData = dict(zip(data.keys(), measurementData))
    # not suitable as a field in InfluxDB due to high cardinality
    del measurementData["timestamp"]

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
    global last_measurement_time
    data = measurement.get("data")
    if (
        data is None
        or data.get("liveMeasurement") is None
        or influxClient is None
        or homeId is None
    ):
        raise Exception("Invalid measurement received %s" % measurement)

    writeMeasurement(influxClient, homeId, data.get("liveMeasurement"))
    last_measurement_time = time.time()


async def tibber_connection(apiEndpoint, apiToken):
    async with aiohttp.ClientSession() as session:
        tibber_connection = tibber.Tibber(
            api_endpoint=apiEndpoint,
            access_token=apiToken,
            websession=session,
            user_agent="tibber-export",
        )
        await tibber_connection.update_info()

        return tibber_connection

async def process_measurements(apiEndpoint, apiToken, influxClient):
    global last_measurement_time
    conn = None

    while True:
        if conn is not None and last_measurement_time > 0:
            if time.time() - last_measurement_time < 60:
                # Measurement received less than 60 seconds ago. Continuing...
                await asyncio.sleep(5)
                continue
            else:
                print("No measurements received for 60 seconds. Restarting connection...")
                print("Closing old connection...")
                await conn.close_connection()
                conn = None
        else:
            if conn is not None:
                print("Closing old connection...")
                await conn.close_connection()
                conn = None

            print("Starting new connection...")    
            try:
                conn = await tibber_connection(apiEndpoint, apiToken)

                home = conn.get_homes()[0]

                callback = partial(process_measurement, influxClient, home.home_id)
                await home.rt_subscribe(callback)
                await asyncio.sleep(15)
            except Exception as e:
                print("Exception caught while connecting to Tibber. Retrying in 5 seconds...")
                print(e)
                await asyncio.sleep(5)
                continue


def sigterm_handler(signal, frame):
    print("Received SIGTERM signal. Exiting gracefully...")
    loop = asyncio.get_running_loop()
    tasks = asyncio.all_tasks(loop=loop)

    for task in tasks:
        task.cancel()

    loop.stop()

    sys.exit(0)


if __name__ == "__main__":
    # Set the SIGTERM signal handler
    signal.signal(signal.SIGTERM, sigterm_handler)

    influxHost = os.getenv("INFLUXDB_HOST")
    influxPort = os.getenv("INFLUXDB_PORT")
    influxDB = os.getenv("INFLUXDB_DB")
    influxUser = os.getenv("INFLUXDB_USER")
    influxPassword = os.getenv("INFLUXDB_PASSWORD")
    tibberApi = os.getenv("TIBBER_API_ENDPOINT")
    tibberToken = os.getenv("TIBBER_API_TOKEN")

    if None in (
        influxHost,
        influxPort,
        influxDB,
        influxUser,
        influxPassword,
        tibberApi,
        tibberToken,
    ):
        print("Incomplete configuration", file=sys.stderr)
        exit(1)
    else:
        print("Retrieving power data from Tibber GraphQL endpoint at %s" % tibberApi)
        print(
            "Sending telemetry to InfluxDB %s on port %s using TLS as user %s using database %s"
            % (influxHost, influxPort, influxUser, influxDB)
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
            loop.run_until_complete(process_measurements(tibberApi, tibberToken, influxClient))
        except Exception as e:
            print("Exception caught: %s" % e, file=sys.stderr)
        finally:
            influxClient.close()
