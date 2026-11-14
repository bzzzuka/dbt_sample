from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator

ENV = {
    "PATH": "/home/airflow/.local/bin:/usr/local/bin:/usr/bin:/bin",
    "MINIO_ENDPOINT": "http://minio:9000",
    "MINIO_ROOT_USER": "minioadmin",
    "MINIO_ROOT_PASSWORD": "minioadmin",
    "MINIO_BUCKET": "dbt-bucket",
    "MINIO_REGION": "us-east-1",
    "LAYER": "stg",
    "ROWS": "100000",
    "CHUNK_SIZE": "10000",
    "COLUMNS_PER_TABLE": "120",
    "WRITE_LOCAL": "false",
    "SCHEMA_JSON_PATH": "/tmp/_schema.json",
    "RETAIL_PREFIX": "retail/stg",
    "RETAIL_SCHEMA_JSON_PATH": "/tmp/_retail_schema.json",
    "RETAIL_ORDERS": "200000",
    "RETAIL_CUSTOMERS": "50000",
    "RETAIL_PRODUCTS": "2000",
    "RETAIL_STORES": "200",
    "RETAIL_PROMOTIONS": "100",
    "RETAIL_REVIEWS": "20000",
    "TRINO_HOST": "trino",
    "TRINO_PORT": "8080",
    "TRINO_USER": "trino",
    "TRINO_CATALOG": "iceberg",
    "TRINO_SCHEMA": "analytics",
    "DBT_PROJECT_DIR": "/opt/airflow/dbt_project",
    "DBT_PROFILES_DIR": "/opt/airflow/dbt_profiles",
}

default_args = {
    "owner": "data-team",
    "retries": 0,
}

with DAG(
    dag_id="dbt_supply_chain_pipeline",
    description="Supply chain + retail: generaciya -> S3 -> Spark/Iceberg -> dbt-trino",
    default_args=default_args,
    start_date=datetime(2026, 1, 1),
    schedule="0 3 * * *",
    catchup=False,
    max_active_runs=1,
    tags=["dbt", "trino", "iceberg", "retail"],
) as dag:

    gen = BashOperator(
        task_id="generate_and_upload",
        bash_command="python /opt/airflow/dbt/scripts/generate_and_upload.py",
        env=ENV,
    )

    retail_gen = BashOperator(
        task_id="generate_retail",
        bash_command="python /opt/airflow/dbt/scripts/generate_retail.py",
        env=ENV,
    )

    spark_etl = BashOperator(
        task_id="spark_etl_to_iceberg",
        bash_command=(
            "spark-submit "
            "--properties-file /opt/airflow/spark/conf/spark-defaults.conf "
            "--master 'local[2]' --driver-memory 3g "
            "/opt/airflow/spark/jobs/etl_all_to_iceberg.py"
        ),
        env=ENV,
    )

    run = BashOperator(
        task_id="dbt_run",
        bash_command=(
            "mkdir -p /tmp/dbt_logs /tmp/dbt_target && "
            "cd /opt/airflow/dbt_project && "
            "dbt --log-path /tmp/dbt_logs run "
            "--profiles-dir /opt/airflow/dbt_profiles "
            "--target-path /tmp/dbt_target"
        ),
        env=ENV,
    )

    test = BashOperator(
        task_id="dbt_test",
        bash_command=(
            "mkdir -p /tmp/dbt_logs /tmp/dbt_target && "
            "cd /opt/airflow/dbt_project && "
            "dbt --log-path /tmp/dbt_logs test "
            "--profiles-dir /opt/airflow/dbt_profiles "
            "--target-path /tmp/dbt_target"
        ),
        env=ENV,
    )

    gen >> retail_gen >> spark_etl >> run >> test
