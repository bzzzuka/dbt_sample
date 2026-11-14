# start-airflow.ps1 - Start Airflow + MinIO + Iceberg + Trino (without Superset).
# Requires Docker Desktop with WSL2, ~8 GB Docker RAM.

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "..\common.ps1")

Assert-Docker

Write-Host "============================================================"
Write-Host "  Start Airflow mode (without Superset)"
Write-Host "============================================================"

try {
    Invoke-Compose stop superset superset-worker superset-dashboards superset-init
} catch {
    Write-Host "Superset services are not running; continuing."
}

Invoke-Compose up -d minio iceberg-rest trino redis
Wait-Healthy minio
Wait-Healthy iceberg-rest
Wait-Trino
Wait-Healthy redis

Invoke-Compose up -d postgres-airflow
Wait-Healthy postgres-airflow

Invoke-Compose up -d airflow-init
Wait-OneShot airflow-init

Invoke-Compose up -d airflow-webserver airflow-scheduler airflow-worker airflow-triggerer
Wait-Healthy airflow-webserver
Wait-Healthy airflow-worker

Write-Access
