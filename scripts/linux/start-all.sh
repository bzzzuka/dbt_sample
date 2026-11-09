#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../common.sh"

require_docker

echo "============================================================"
echo "  Start FULL stack: StarRocks + MinIO + dbt + Superset + Airflow"
echo "============================================================"

dc config --quiet
dc up -d --build

wait_one_shot data-init
wait_starrocks
wait_one_shot dbt

wait_one_shot superset-init
wait_healthy superset
wait_one_shot superset-dashboards
wait_healthy superset-worker

wait_one_shot airflow-init
wait_healthy airflow-webserver
wait_healthy airflow-worker

wait_healthy minio
wait_healthy postgres-airflow
wait_healthy redis
wait_healthy iceberg-rest

print_access
