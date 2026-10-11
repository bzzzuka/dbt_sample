#!/usr/bin/env bash
set -euo pipefail

cd /dbt/project
dbt debug
dbt run
dbt test
echo "dbt: успешно завершено"