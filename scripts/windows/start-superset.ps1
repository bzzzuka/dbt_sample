# start-superset.ps1 - Start Superset + StarRocks + MinIO + dbt (without Airflow).
# Requires Docker Desktop with WSL2, ~4.8 GB Docker RAM.

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

Invoke-Compose up -d starrocks minio redis
Wait-StarRocks
Wait-Healthy minio
Wait-Healthy redis

Invoke-Compose up -d data-init dbt
Wait-OneShot data-init
Wait-OneShot dbt

Invoke-Compose up -d superset-init
Wait-OneShot superset-init

Invoke-Compose up -d superset superset-worker superset-dashboards
Wait-Healthy superset
Wait-Healthy superset-worker
Wait-OneShot superset-dashboards

Write-Access
