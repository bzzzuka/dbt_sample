#!/usr/bin/env bash
set -euo pipefail

echo "============================================================"
echo "  data-init: генерация -> S3 -> StarRocks"
echo "============================================================"

echo
echo ">>> [1/4] Генерация supply_chain и загрузка в MinIO (S3)"
python /dbt/scripts/generate_and_upload.py

echo
echo ">>> [2/4] Загрузка supply_chain из MinIO (S3) в StarRocks"
python /dbt/scripts/load_s3_to_starrocks.py

echo
echo ">>> [3/4] Генерация retail и загрузка в MinIO (S3)"
python /dbt/scripts/generate_retail.py

echo
echo ">>> [4/4] Загрузка retail из MinIO (S3) в StarRocks"
python /dbt/scripts/load_retail_to_starrocks.py

echo
echo "============================================================"
echo "  data-init: готово"
echo "============================================================"