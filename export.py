import os
import sys
import json
import asyncio
import aiohttp
import dateutil.parser
import tibber
from influxdb import InfluxDBClient
from functools import partial


def createInfluxPoint(data, homeId):
    timestamp = dateutil.parser.isoparse(data.get("timestamp"))
    timestamp_ns = int(timestamp.timestamp() * 1e9) # influxdb timestamp in nanoseconds

    measurementData = dict(data)
    # not suitable as a field in InfluxDB due to high cardinality
    del measurementData["timestamp"]

    return {
        "measurement": "tibber-measurement",
        "tags": {
            "home_id": homeId
        },
        "timestamp": timestamp_ns,
        "fields": measurementData
    }


def writeMeasurement(influxClient: InfluxDBClient, homeId: str, measurement: dict):
    point = createInfluxPoint(measurement, homeId)
    influxClient.write_points([point])


def process_measurement(influxClient: InfluxDBClient, homeId: str, measurement: dict):
    data = measurement.get("data")
    if data is None or data.get("liveMeasurement") is None or influxClient is None or homeId is None:
        raise Exception("Invalid measurement received %s" % measurement)

    writeMeasurement(influxClient, homeId, data.get("liveMeasurement"))


async def process_measurements(apiEndpoint, apiToken, influxClient):
    async with aiohttp.ClientSession() as session:
        tibber_connection = tibber.Tibber(
            api_endpoint=apiEndpoint, access_token=apiToken, websession=session, user_agent="tibber-export")
        await tibber_connection.update_info()
    home = tibber_connection.get_homes()[0]

    callback = partial(process_measurement, influxClient, home.home_id)
    await home.rt_subscribe(callback)

    while True:
        await asyncio.sleep(5)

if __name__ == '__main__':

    influxHost = os.getenv("INFLUXDB_HOST")
    influxPort = os.getenv("INFLUXDB_PORT")
    influxDB = os.getenv("INFLUXDB_DB")
    influxUser = os.getenv("INFLUXDB_USER")
    influxPassword = os.getenv("INFLUXDB_PASSWORD")
    tibberApi = os.getenv("TIBBER_API_ENDPOINT")
    tibberToken = os.getenv("TIBBER_API_TOKEN")

    if None in (influxHost, influxPort, influxDB, influxUser, influxPassword, tibberApi, tibberToken):
        print("Incomplete configuration", file=sys.stderr)
        exit(1)
    else:
        print("Retrieving power data from Tibber GraphQL endpoint at %s" % tibberApi)
        print("Sending telemetry to InfluxDB %s on port %s using TLS as user %s using database %s" % (
            influxHost, influxPort, influxUser, influxDB))

    while True:
        try:
            influxClient = InfluxDBClient(host=influxHost, port=influxPort, username=influxUser,
                                          password=influxPassword, database=influxDB, ssl=True, verify_ssl=True)

            loop = asyncio.get_event_loop()
            loop.run_until_complete(process_measurements(
                tibberApi, tibberToken, influxClient))
        except Exception as e:
            print("Exception caught: %s" % e, file=sys.stderr)
        finally:
            influxClient.close()
