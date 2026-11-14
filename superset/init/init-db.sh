#!/usr/bin/env bash
set -e

TRINO_URL="http://${TRINO_HOST:-trino}:${TRINO_PORT:-8080}/v1/info"

echo "============================================================"
echo "  Superset init"
echo "============================================================"

echo "Ожидание Trino (${TRINO_URL})..."
until curl -fsS "${TRINO_URL}" >/dev/null 2>&1; do
    sleep 3
done
echo "Trino доступен."

echo
echo ">>> Миграции Superset"
superset db upgrade

echo
echo ">>> Создание админа (admin/admin)"
superset fab create-admin \
    --username admin \
    --firstname Admin \
    --lastname User \
    --email admin@example.com \
    --password admin || true

echo
echo ">>> Инициализация ролей и прав"
superset init

echo
echo ">>> Добавление подключения к Trino"
python /app/init/add_trino_db.py

echo
echo "============================================================"
echo "  Superset init завершён"
echo "============================================================"
