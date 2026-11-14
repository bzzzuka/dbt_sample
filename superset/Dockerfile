FROM apache/superset:4.1.2

USER root

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl python3-pip python3-venv \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-local.txt /app/docker/requirements-local.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/docker/requirements-local.txt

USER superset
