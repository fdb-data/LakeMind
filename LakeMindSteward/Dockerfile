FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --upgrade pip && pip install .

ENV LAKE_CONFIG=/etc/lakemind/config.yaml
EXPOSE 8500
CMD ["python", "-m", "lakemind_steward"]
