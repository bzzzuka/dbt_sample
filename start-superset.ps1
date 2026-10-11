# start-superset.ps1 - Запуск Superset + StarRocks + MinIO + dbt (без Airflow)
# Подходит для 4.8 ГБ Docker RAM.

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
Set-Location $root

Write-Host "=== Запуск Superset без Airflow ===" -ForegroundColor Cyan

# 1. Останавливаем Airflow
Write-Host "`n[1/5] Останавливаем Airflow..." -ForegroundColor Yellow
docker compose stop airflow-webserver airflow-scheduler airflow-worker airflow-triggerer 2>$null
Start-Sleep -Seconds 5

# 2. База
Write-Host "`n[2/5] StarRocks + MinIO..." -ForegroundColor Yellow
docker compose up -d starrocks minio
Start-Sleep -Seconds 60

# 3. Данные и dbt
Write-Host "`n[3/5] data-init + dbt..." -ForegroundColor Yellow
docker compose up -d data-init dbt
Start-Sleep -Seconds 30

# 4. Superset
Write-Host "`n[4/5] Superset..." -ForegroundColor Yellow
docker compose up -d superset-init
Start-Sleep -Seconds 60
docker compose up -d superset

# 5. Проверка
Write-Host "`n[5/5] Статус..." -ForegroundColor Yellow
Start-Sleep -Seconds 15
docker compose ps | Select-String "superset|starrocks|minio|dbt"

Write-Host "`n=== Готово ===" -ForegroundColor Green
Write-Host "Superset:  http://localhost:8088  (admin/admin)" -ForegroundColor White
Write-Host "MinIO:     http://localhost:9001  (minioadmin/minioadmin)" -ForegroundColor White
Write-Host "`nВернуть Airflow: .\start-airflow.ps1" -ForegroundColor DarkGray