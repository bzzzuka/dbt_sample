#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../common.sh"

require_docker

echo "============================================================"
echo "  Start Superset mode (without Airflow)"
echo "============================================================"

dc config --quiet
dc stop airflow-webserver airflow-scheduler airflow-worker airflow-triggerer 2>/dev/null || true

dc up -d starrocks minio redis
wait_starrocks
wait_healthy minio
wait_healthy redis

dc up -d data-init dbt
wait_one_shot data-init
wait_one_shot dbt

dc up -d superset-init
wait_one_shot superset-init

dc up -d superset superset-worker superset-dashboards
wait_healthy superset
wait_healthy superset-worker
wait_one_shot superset-dashboards

print_access
