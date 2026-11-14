# Архитектура проекта (Trino + Iceberg)

**Актуально на:** 2026-11-13

**Стек:** synthetic data → MinIO/S3 → Spark → Iceberg → Trino → dbt-trino → Superset.

StarRocks удалён. Trino — единственный SQL-слой, все данные в Iceberg.

---

## 1. Поток данных

```
generate_and_upload.py / generate_retail.py
        |
        v
MinIO (dbt-bucket)
  ├── stg/{table}/{date}/*.csv
  └── retail/stg/{table}/{date}/*.csv
        |
        v
spark/jobs/etl_all_to_iceberg.py
        |
        v
Iceberg tables в S3
  lakehouse.analytics.raw_*
  lakehouse.analytics.raw_retail_*
        |
        v
Iceberg REST catalog (iceberg-rest:8181)
        |
        v
Trino (iceberg.analytics)
        |
        v
dbt-trino
  ├── staging views (26)
  └── marts tables (11)
        |
        v
Superset / DBeaver
```

---

## 2. Сервисы

| Сервис | Образ | Роль | Порты |
|---|---|---|---|
| `minio` | coollabsio/minio | S3 | 9000, 9001 |
| `data-init` | ./dbt | генерация CSV в S3 | — |
| `spark-etl` | apache/spark:3.5.6 | CSV → Iceberg | — |
| `iceberg-rest` | apache/iceberg-rest-fixture:1.10.1 | Iceberg catalog | 8181 |
| `trino` | trinodb/trino:484 | SQL-движок | **8081 → 8080** |
| `dbt` | ./dbt | dbt-trino run/test | — |
| `superset` | ./superset | BI | 8088 |
| `superset-init` | ./superset | Trino connection | — |
| `superset-worker` | ./superset | Celery worker | — |
| `superset-dashboards` | ./superset | дашборды | — |
| `postgres-airflow` | postgres:15-alpine | метаданные Airflow | — |
| `redis` | redis:7-alpine | Celery + Superset results | 6379 |
| `airflow-*` | ./airflow | оркестрация | 8080 |
| `spark-iceberg` | apache/spark:3.5.6 | Spark UI/manual | 4040 |

StarRocks больше нет.

---

## 3. Порты

| Порт | Сервис |
|---|---|
| 8080 | Airflow |
| **8081** | **Trino** |
| 8088 | Superset |
| 8181 | Iceberg REST |
| 9000 / 9001 | MinIO |
| 4040 | Spark UI |

---

## 4. Volumes

| Volume | Кто использует | Что хранит |
|---|---|---|
| `minio_data` | minio | CSV + Iceberg warehouse |
| `iceberg_catalog_data` | iceberg-rest | metadata каталога (`/tmp`) |
| `superset_home` | Superset | metadata |
| `postgres_airflow_data` | Postgres | метаданные Airflow |

`iceberg_catalog_data` важен: без него Iceberg REST теряет таблицы при
пересоздании контейнера.

---

## 5. Слои данных

| Слой | Где | Имена |
|---|---|---|
| Raw supply | Iceberg `analytics` | `raw_{table}` |
| Raw retail | Iceberg `analytics` | `raw_retail_{table}` |
| Staging | Trino views | `stg_*`, `stg_retail__*` |
| Marts | Trino/Iceberg tables | `mart_*`, `mart_retail__*` |

Все таблицы — Iceberg/Parquet в S3.

---

## 6. dbt-trino

- `dbt/profiles/profiles.yml` — Trino (`host=trino`, `port=8080`,
  `database=iceberg`, `schema=analytics`);
- staging — views;
- marts — tables с `format='PARQUET'`;
- 37 моделей, 19 тестов.

---

## 7. Airflow

DAG `dbt_supply_chain_pipeline`:

```
generate_and_upload
  -> generate_retail
  -> spark_etl_to_iceberg
  -> dbt_run
  -> dbt_test
```

Airflow worker содержит `pyspark` и `dbt-trino`; Spark job запускается
через `spark-submit --properties-file /opt/airflow/spark/conf/spark-defaults.conf`.

---

## 8. Superset

- подключение `Trino Iceberg`:
  `trino://trino@trino:8080/iceberg/analytics`;
- 11 datasets, 16 charts, 2 dashboards;
- `superset-dashboards` создаёт их идемпотентно.

---

## 9. Принципы

1. Trino не хранит данные.
2. Iceberg — единый формат для Spark/Trino/dbt.
3. StarRocks не используется.
4. Один каталог `iceberg`, одна schema `analytics`.
5. One-shot сервисы завершаются `Exited (0)`.

---

## 10. Ограничения

- Iceberg REST fixture — учебный; в production нужен JDBC/Nessie.
- Нет партиционирования Iceberg по датам.
- Trino без marts бесполезен: сначала Spark ETL, затем dbt.
- Airflow Spark — `local[2]` в worker, не отдельный кластер.

---

## 11. Связанные документы

- [`RUNBOOK.md`](RUNBOOK.md)
- [`modules/05-trino.md`](modules/05-trino.md)
- [`modules/06-spark-iceberg.md`](modules/06-spark-iceberg.md)
- [`../trino_migration.md`](../trino_migration.md)
