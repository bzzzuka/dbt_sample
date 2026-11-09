# start-all.ps1 - Start the whole stack on Windows.
# Requires Docker Desktop with WSL2, >= 8 GB Docker RAM.

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "..\common.ps1")

Assert-Docker

Write-Host "============================================================"
Write-Host "  Start FULL stack: StarRocks + MinIO + dbt + Superset + Airflow"
Write-Host "============================================================"

Invoke-Compose config --quiet
Invoke-Compose up -d --build

Wait-OneShot data-init
Wait-StarRocks
Wait-OneShot dbt

Wait-OneShot superset-init
Wait-Healthy superset
Wait-OneShot superset-dashboards
Wait-Healthy superset-worker

Wait-OneShot airflow-init
Wait-Healthy airflow-webserver
Wait-Healthy airflow-worker

Wait-Healthy minio
Wait-Healthy postgres-airflow
Wait-Healthy redis
Wait-Healthy iceberg-rest

Write-Access
