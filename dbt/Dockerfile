FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl && rm -rf /var/lib/apt/lists/*

WORKDIR /dbt

# venv
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# dbt 1.7.0 + вспомогательные библиотеки для генерации/загрузки данных
# protobuf==4.25.3 фиксируем: dbt-core 1.7.0 несовместим с protobuf 5.x
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    dbt-core==1.7.0 \
    dbt-postgres==1.7.0 \
    protobuf==4.25.3 \
    boto3 \
    psycopg2-binary \
    pandas \
    sqlalchemy

# Профили dbt
COPY profiles/profiles.yml /dbt/profiles/profiles.yml
ENV DBT_PROFILES_DIR=/dbt/profiles

# Скрипты
COPY scripts/ /dbt/scripts/
RUN chmod +x /dbt/scripts/*.sh && mkdir -p /dbt/project

CMD ["bash"]