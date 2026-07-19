FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir httpx psycopg2-binary redis

COPY src/ /app/src/

ENV PYTHONPATH=/app/src

RUN useradd -r -u 1000 telemetry && chown -R telemetry:telemetry /app
USER telemetry

CMD ["python", "-m", "lakemind_telemetry_agent"]
