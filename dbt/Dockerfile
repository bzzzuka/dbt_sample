FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl default-mysql-client && rm -rf /var/lib/apt/lists/*

WORKDIR /dbt

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --no-cache-dir --upgrade pip && \
    pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip config set global.trusted-host pypi.tuna.tsinghua.edu.cn

# 1. Совместимая пара: dbt-core 1.6.2 + dbt-starrocks 1.6.2
RUN pip install --no-cache-dir \
    dbt-core==1.6.2 \
    dbt-starrocks==1.6.2

# 2. Принудительный откат драйвера на 8.0.22 (лечит баг server_version)
RUN pip install --no-cache-dir --force-reinstall --no-deps \
    mysql-connector-python==8.0.22

# 3. Остальные утилиты
RUN pip install --no-cache-dir \
    boto3 \
    pandas \
    requests

COPY profiles/profiles.yml /dbt/profiles/profiles.yml
ENV DBT_PROFILES_DIR=/dbt/profiles

COPY scripts/ /dbt/scripts/
RUN chmod +x /dbt/scripts/*.sh && mkdir -p /dbt/project

CMD ["bash"]