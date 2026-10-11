# start-all.ps1 - Start the whole stack: StarRocks + MinIO + dbt + Superset + Airflow
# Requires >= 7 GB Docker RAM. Will OOM at 4.8 GB.

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
Set-Location $root

Write-Host "=== Start FULL stack ===" -ForegroundColor Cyan
Write-Host "Components: StarRocks, MinIO, dbt, Superset, Airflow" -ForegroundColor Gray

# 1. Base
Write-Host "`n[1/5] StarRocks + MinIO..." -ForegroundColor Yellow
docker compose up -d starrocks minio
Start-Sleep -Seconds 60

# 2. Data + dbt
Write-Host "`n[2/5] data-init + dbt..." -ForegroundColor Yellow
docker compose up -d data-init dbt
Start-Sleep -Seconds 30

# 3. Superset
Write-Host "`n[3/5] Superset..." -ForegroundColor Yellow
docker compose up -d superset-init
Start-Sleep -Seconds 60
docker compose up -d superset

# 4. Airflow
Write-Host "`n[4/5] Airflow init..." -ForegroundColor Yellow
docker compose up -d postgres-airflow redis
Start-Sleep -Seconds 20
docker compose up -d airflow-init
Start-Sleep -Seconds 30
docker compose up -d airflow-webserver airflow-scheduler airflow-worker airflow-triggerer

# 5. Status
Write-Host "`n[5/5] Status..." -ForegroundColor Yellow
Start-Sleep -Seconds 20
docker compose ps

Write-Host "`n=== Done ===" -ForegroundColor Green
Write-Host "Airflow:   http://localhost:8080  (admin/admin)" -ForegroundColor White
Write-Host "Superset:  http://localhost:8088  (admin/admin)" -ForegroundColor White
Write-Host "MinIO:     http://localhost:9001  (minioadmin/minioadmin)" -ForegroundColor White
Write-Host "StarRocks: http://localhost:8030  (root/empty)" -ForegroundColor White