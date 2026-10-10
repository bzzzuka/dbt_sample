#!/usr/bin/env bash
set -euo pipefail

echo "============================================================"
echo "  data-init: генерация → S3 → Postgres"
echo "============================================================"

echo
echo ">>> [1/2] Генерация бизнес-данных о поставках и загрузка в MinIO (S3)"
python /dbt/scripts/generate_and_upload.py

echo
echo ">>> [2/2] Загрузка данных из MinIO (S3) в Postgres"
python /dbt/scripts/load_s3_to_postgres.py

echo
echo "============================================================"
echo "  data-init: готово"
echo "============================================================"