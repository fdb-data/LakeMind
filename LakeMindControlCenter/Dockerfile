FROM node:20-alpine AS frontend-build
WORKDIR /build
COPY frontend/package.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx supervisor \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip && pip install \
    fastapi==0.115.6 \
    uvicorn==0.34.0 \
    httpx==0.28.1 \
    pydantic==2.11.3

WORKDIR /app
COPY bff/app.py ./bff/app.py
COPY steward/app.py ./steward/app.py
COPY steward/steward_service.py ./steward/steward_service.py

COPY --from=frontend-build /build/dist /usr/share/nginx/html

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY supervisord.conf /etc/supervisor/conf.d/lakemind.conf

RUN rm -f /etc/nginx/sites-enabled/default

EXPOSE 3000
CMD ["supervisord", "-n", "-c", "/etc/supervisor/conf.d/lakemind.conf"]
