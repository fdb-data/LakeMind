FROM lakemind/server-api:latest
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir litellm>=1.40 funasr>=1.0 python-multipart>=0.0.9
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir --no-deps .
ENV LAKE_CONFIG=/etc/lakemind/models.yaml
EXPOSE 10824
CMD ["python", "-m", "lakemind_model_serving"]
