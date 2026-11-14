# Модуль 06 — Spark + Iceberg

**Файлы:**

- `spark/conf/spark-defaults.conf`
- `spark/jobs/etl_all_to_iceberg.py`
- `spark/jobs/etl_supply_chain.py`
- сервисы `spark-etl`, `spark-iceberg`, `iceberg-rest`

---

## 1. Роль

Spark — единственный writer raw-слоя в Iceberg.

```
CSV в MinIO -> Spark -> Iceberg tables (S3) -> Iceberg REST -> Trino
```

StarRocks из схемы удалён.

---

## 2. Конфиг

`spark/conf/spark-defaults.conf`:

- каталог `lakehouse`, type `rest`, `http://iceberg-rest:8181`;
- warehouse `s3://dbt-bucket/warehouse`;
- S3FileIO + MinIO;
- память 4g;
- Ivy cache `/tmp/.ivy2`.

---

## 3. Загрузка

`etl_all_to_iceberg.py`:

- `raw_{table}` — 15 supply-таблиц;
- `raw_retail_{table}` — 11 retail-таблиц.

Запуск:

```powershell
docker compose run --rm --no-deps spark-etl
```

Сервис `spark-etl` — one-shot, запускается после `data-init`.

---

## 4. Проверка

```powershell
docker exec spark_iceberg /opt/spark/bin/spark-submit `
  /opt/spark/jobs/verify_iceberg.py
```

Или через Trino:

```sql
SHOW TABLES FROM iceberg.analytics;
SELECT COUNT(*) FROM iceberg.analytics.raw_suppliers;
```

---

## 5. Iceberg REST

`iceberg-rest-fixture` хранит metadata в `/tmp`. В compose `/tmp`
смонтирован в volume `iceberg_catalog_data`, поэтому metadata переживают
пересоздание контейнера.

Для production нужен JDBC/Nessie.

---

## 6. Ограничения

- `inferSchema` для supply-таблиц может дать double вместо decimal.
- Нет partitioning.
- Spark ETL не incremental.
- Первый запуск скачивает Maven-зависимости.

---

## 7. Связанные документы

- [`05-trino.md`](05-trino.md)
- [`07-minio.md`](07-minio.md)
- [`../DEVELOPMENT_GUIDE.md`](../DEVELOPMENT_GUIDE.md)
