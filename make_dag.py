from pathlib import Path

DAG = '''from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator

ENV = {
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
    "DBT_PROFILES_DIR": "/opt/airflow/dbt_profiles",
}

default_args = {
    "owner": "data-team",
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
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
        bash_command="cd /opt/airflow/dbt_project && dbt run --profiles-dir /opt/airflow/dbt_profiles",
        env=ENV,
    )

    test = BashOperator(
        task_id="dbt_test",
        bash_command="cd /opt/airflow/dbt_project && dbt test --profiles-dir /opt/airflow/dbt_profiles",
        env=ENV,
    )

    gen >> load >> run >> test
'''

out = Path("airflow/dags/dbt_supply_chain_dag.py")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(DAG, encoding="utf-8", newline="\n")
print(f"OK: {out} ({out.stat().st_size} bytes)")