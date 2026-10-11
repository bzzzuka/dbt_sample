from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator

ENV = {
    "PATH": "/home/airflow/.local/bin:/usr/local/bin:/usr/bin:/bin",
    "STARROCKS_HOST": "starrocks",
    "STARROCKS_PORT": "9030",
    "STARROCKS_USER": "root",
    "STARROCKS_PASSWORD": "",
    "STARROCKS_SCHEMA": "analytics",
    "STARROCKS_CATALOG": "default_catalog",
    "MINIO_ENDPOINT": "http://minio:9000",
    "MINIO_ROOT_USER": "minioadmin",
    "MINIO_ROOT_PASSWORD": "minioadmin",
    "MINIO_BUCKET": "dbt-bucket",
    "MINIO_REGION": "us-east-1",
    "LAYER": "stg",
    "ROWS": "5000",
    "CHUNK_SIZE": "2500",
    "COLUMNS_PER_TABLE": "120",
    "WRITE_LOCAL": "false",
    "SCHEMA_JSON_PATH": "/tmp/_schema.json",
    "DBT_PROJECT_DIR": "/opt/airflow/dbt_project",
    "DBT_PROFILES_DIR": "/opt/airflow/dbt_profiles",
}

default_args = {
    "owner": "data-team",
    "retries": 0,
}

with DAG(
    dag_id="dbt_supply_chain_pipeline",
    description="Generaciya -> S3 -> StarRocks -> dbt",
    default_args=default_args,
    start_date=datetime(2026, 1, 1),
    schedule="0 3 * * *",
    catchup=False,
    max_active_runs=1,
    tags=["dbt", "starrocks"],
) as dag:

    gen = BashOperator(
        task_id="generate_and_upload",
        bash_command="python /opt/airflow/dbt/scripts/generate_and_upload.py",
        env=ENV,
    )

    load = BashOperator(
        task_id="load_to_starrocks",
        bash_command="python /opt/airflow/dbt/scripts/load_s3_to_starrocks.py",
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

    gen >> load >> run >> test