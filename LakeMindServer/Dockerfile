FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml ./
COPY src ./src
RUN pip install --upgrade pip && pip install .
ENV LAKE_CONFIG=/etc/lakemind/engines.yaml
EXPOSE 10823
CMD ["python", "-m", "lakemind_server"]
