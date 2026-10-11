# start-airflow.ps1 - Start Airflow + StarRocks + MinIO + dbt (without Superset)
# Requires ~4 GB Docker RAM.

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
Set-Location $root

Write-Host "=== Start Airflow (without Superset) ===" -ForegroundColor Cyan

# 1. Stop Superset
Write-Host "`n[1/6] Stopping Superset..." -ForegroundColor Yellow
docker compose stop superset superset-init superset-worker 2>$null
Start-Sleep -Seconds 5

# 2. Base
Write-Host "`n[2/6] StarRocks + MinIO..." -ForegroundColor Yellow
docker compose up -d starrocks minio
Start-Sleep -Seconds 60

# 3. Data + dbt
Write-Host "`n[3/6] data-init + dbt..." -ForegroundColor Yellow
docker compose up -d data-init dbt
Start-Sleep -Seconds 30

# 4. Airflow metadata DB
Write-Host "`n[4/6] Airflow Postgres + Redis..." -ForegroundColor Yellow
docker compose up -d postgres-airflow redis
Start-Sleep -Seconds 20

# 5. Airflow init
Write-Host "`n[5/6] Airflow init..." -ForegroundColor Yellow
docker compose up -d airflow-init
Start-Sleep -Seconds 30
docker compose logs airflow-init --tail 5

# 6. Airflow services
Write-Host "`n[6/6] Airflow webserver + scheduler + triggerer..." -ForegroundColor Yellow
docker compose up -d airflow-webserver airflow-scheduler airflow-triggerer
Start-Sleep -Seconds 20
docker compose ps | Select-String "airflow"

Write-Host "`n=== Done ===" -ForegroundColor Green
Write-Host "Airflow:   http://localhost:8080  (admin/admin)" -ForegroundColor White
Write-Host "MinIO:     http://localhost:9001  (minioadmin/minioadmin)" -ForegroundColor White
Write-Host "StarRocks: http://localhost:8030  (root/empty)" -ForegroundColor White
Write-Host "`nSwitch to Superset: .\start-superset.ps1" -ForegroundColor DarkGray