FROM apache/airflow:2.10.5-python3.11

USER airflow

RUN pip install --no-cache-dir --upgrade pip && \
    pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip config set global.trusted-host pypi.tuna.tsinghua.edu.cn

RUN pip install --no-cache-dir \
    apache-airflow-providers-common-sql \
    astronomer-cosmos \
    dbt-core==1.6.2 \
    dbt-starrocks==1.6.2 \
    pandas \
    requests

# Принудительный откат драйвера на 8.0.33
RUN pip install --no-cache-dir --force-reinstall --no-deps \
    mysql-connector-python==8.0.33