# start-superset.ps1 - Start Superset + Trino + Iceberg + MinIO (without Airflow).
# Requires Docker Desktop with WSL2, ~8 GB Docker RAM.

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "..\common.ps1")

Assert-Docker

Write-Host "============================================================"
Write-Host "  Start Superset mode (without Airflow)"
Write-Host "============================================================"

try {
    Invoke-Compose stop airflow-webserver airflow-scheduler airflow-worker airflow-triggerer
} catch {
    Write-Host "Airflow services are not running; continuing."
}

Invoke-Compose up -d minio iceberg-rest trino redis
Wait-Healthy minio
Wait-Healthy iceberg-rest
Wait-Trino
Wait-Healthy redis

Invoke-Compose up -d data-init spark-etl dbt
Wait-OneShot data-init
Wait-OneShot spark-etl
Wait-OneShot dbt

Invoke-Compose up -d superset-init
Wait-OneShot superset-init

Invoke-Compose up -d superset superset-worker superset-dashboards
Wait-Healthy superset
Wait-Healthy superset-worker
Wait-OneShot superset-dashboards

Write-Access
