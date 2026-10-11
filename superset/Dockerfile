FROM apache/superset:4.1.2

USER root

# Системные зависимости: компилятор для mysqlclient + pip/venv + mysql-клиент
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-libmysqlclient-dev build-essential pkg-config python3-dev \
    python3-pip python3-venv default-mysql-client \
    && rm -rf /var/lib/apt/lists/*

# Установка драйверов через системный pip (он пишет в /app/.venv)
COPY requirements-local.txt /app/docker/requirements-local.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/docker/requirements-local.txt

USER superset