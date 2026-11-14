FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl && rm -rf /var/lib/apt/lists/*

WORKDIR /dbt

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --no-cache-dir --upgrade pip && \
    pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip config set global.trusted-host pypi.tuna.tsinghua.edu.cn && \
    pip install --no-cache-dir \
    dbt-core==1.6.2 \
    dbt-trino==1.6.2 \
    boto3 \
    pandas \
    requests

COPY profiles/profiles.yml /dbt/profiles/profiles.yml
ENV DBT_PROFILES_DIR=/dbt/profiles

COPY scripts/ /dbt/scripts/
RUN chmod +x /dbt/scripts/*.sh && mkdir -p /dbt/project

CMD ["bash"]
