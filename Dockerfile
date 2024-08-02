FROM python:3.11-alpine

ENV INFLUXDB_HOST="" \
    INFLUXDB_PORT="" \
    INFLUXDB_DB="" \
    INFLUXDB_USER="" \
    INFLUXDB_PASSWORD="" \
    TIBBER_API_ENDPOINT="" \
    TIBBER_API_TOKEN=""

COPY export.py requirements.txt /app/
WORKDIR /app

RUN pip install -r requirements.txt

ENTRYPOINT ["python", "export.py"] 
