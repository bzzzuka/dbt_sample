#!/usr/bin/env bash
set -euo pipefail

echo "============================================================"
echo "  data-init: synthetic data -> MinIO/S3"
echo "============================================================"

echo
echo ">>> [1/2] Генерация supply_chain и загрузка в MinIO (S3)"
python /dbt/scripts/generate_and_upload.py

echo
echo ">>> [2/2] Генерация retail и загрузка в MinIO (S3)"
python /dbt/scripts/generate_retail.py

echo
echo "============================================================"
echo "  data-init: готово (Iceberg загрузит spark-etl)"
echo "============================================================"
