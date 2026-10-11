#!/usr/bin/env bash
set -e

echo "============================================================"
echo "  Superset init"
echo "============================================================"

echo "Ожидание StarRocks (${STARROCKS_HOST}:${STARROCKS_PORT})..."
until mysql -h "${STARROCKS_HOST}" -P "${STARROCKS_PORT}" -u"${STARROCKS_USER}" \
        -e "SELECT 1" >/dev/null 2>&1; do
    sleep 3
done
echo "StarRocks доступен."

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
echo ">>> Добавление подключения к StarRocks"
python /app/init/add_starrocks_db.py

echo
echo "============================================================"
echo "  Superset init завершён"
echo "============================================================"