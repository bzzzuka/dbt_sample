# Spark + Iceberg

Spark читает CSV из MinIO и пишет Iceberg:

- `spark/jobs/etl_all_to_iceberg.py` — 15 supply + 11 retail;
- `spark/conf/spark-defaults.conf` — REST catalog + MinIO/S3.

Запуск:

```powershell
docker compose run --rm --no-deps spark-etl
```

Сервис `spark-etl` — one-shot, выполняется после `data-init`.

Проверка через Trino:

```sql
SHOW TABLES FROM iceberg.analytics;
SELECT COUNT(*) FROM iceberg.analytics.raw_suppliers;
```

StarRocks external catalog удалён.
