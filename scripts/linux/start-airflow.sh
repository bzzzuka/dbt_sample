#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../common.sh"

require_docker

echo "============================================================"
echo "  Start Airflow mode (without Superset)"
echo "============================================================"

dc config --quiet
dc stop superset superset-worker superset-dashboards superset-init 2>/dev/null || true

dc up -d starrocks minio redis
wait_starrocks
wait_healthy minio
wait_healthy redis

dc up -d data-init dbt
wait_one_shot data-init
wait_one_shot dbt

dc up -d postgres-airflow
wait_healthy postgres-airflow

dc up -d airflow-init
wait_one_shot airflow-init

dc up -d airflow-webserver airflow-scheduler airflow-worker airflow-triggerer
wait_healthy airflow-webserver
wait_healthy airflow-worker

print_access
