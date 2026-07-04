FROM postgres:16

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libicu-dev \
        postgresql-server-dev-16 \
        flex \
        bison \
    && rm -rf /var/lib/apt/lists/*

COPY age-src /tmp/age
RUN cd /tmp/age \
    && make PG_CONFIG=/usr/lib/postgresql/16/bin/pg_config \
    && make PG_CONFIG=/usr/lib/postgresql/16/bin/pg_config install \
    && rm -rf /tmp/age
