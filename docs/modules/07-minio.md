# Модуль 07 — MinIO (S3)

**Файлы:** сервис `minio`, `spark/jobs/etl_all_to_iceberg.py`,
`trino/etc/catalog/iceberg.properties`.

---

## 1. Роль

MinIO хранит:

- CSV supply/retail;
- Iceberg warehouse (Parquet + metadata).

Trino и Spark читают S3 напрямую. StarRocks из схемы удалён.

---

## 2. Доступ

| Параметр | Значение |
|---|---|
| S3 API | http://localhost:9000 |
| Console | http://localhost:9001 |
| Access key | minioadmin |
| Secret key | minioadmin |
| Bucket | dbt-bucket |

---

## 3. Структура

```
dbt-bucket/
├── stg/{table}/{date}/*.csv
├── retail/stg/{table}/{date}/*.csv
└── warehouse/
    └── analytics.db/...
```

Iceberg таблицы физически — в `warehouse/`.

---

## 4. mc

```powershell
docker exec dbt_minio mc alias set local http://localhost:9000 minioadmin minioadmin
docker exec dbt_minio mc ls local/dbt-bucket
docker exec dbt_minio mc ls --recursive local/dbt-bucket/stg/suppliers
docker exec dbt_minio mc ls --recursive local/dbt-bucket/warehouse
```

---

## 5. Как читается

- Spark: `s3a://dbt-bucket/...`;
- Trino: `fs.s3.enabled=true`, `s3.endpoint=http://minio:9000`,
  `s3.path-style-access=true`.

---

## 6. Очистка

```powershell
# CSV supply
docker exec dbt_minio mc rm --recursive --force local/dbt-bucket/stg
# CSV retail
docker exec dbt_minio mc rm --recursive --force local/dbt-bucket/retail
# Iceberg
docker exec dbt_minio mc rm --recursive --force local/dbt-bucket/warehouse
```

После очистки Iceberg нужно заново запустить `spark-etl`.

---

## 7. Связанные документы

- [`06-spark-iceberg.md`](06-spark-iceberg.md)
- [`05-trino.md`](05-trino.md)
- [`../RUNBOOK.md`](../RUNBOOK.md)
