FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl default-mysql-client && rm -rf /var/lib/apt/lists/*

WORKDIR /dbt

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Зеркало PyPI (Tsinghua, обычно 10-50 МБ/с из РФ)
RUN pip install --no-cache-dir --upgrade pip && \
    pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip config set global.trusted-host pypi.tuna.tsinghua.edu.cn && \
    pip install --no-cache-dir \
    dbt-core==1.9.0 \
    dbt-starrocks==1.9.0 \
    boto3 \
    pymysql \
    pandas \
    requests

COPY profiles/profiles.yml /dbt/profiles/profiles.yml
ENV DBT_PROFILES_DIR=/dbt/profiles

COPY scripts/ /dbt/scripts/
RUN chmod +x /dbt/scripts/*.sh && mkdir -p /dbt/project

CMD ["bash"]