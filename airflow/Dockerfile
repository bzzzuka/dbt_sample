FROM apache/airflow:2.10.5-python3.11

USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    openjdk-17-jre-headless procps && rm -rf /var/lib/apt/lists/*

USER airflow

RUN pip install --no-cache-dir --upgrade pip && \
    pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip config set global.trusted-host pypi.tuna.tsinghua.edu.cn

RUN pip install --no-cache-dir \
    "apache-airflow==2.10.5" \
    dbt-core==1.6.2 \
    dbt-trino==1.6.2 \
    pyspark==3.5.6 \
    boto3 \
    botocore \
    pandas \
    requests
