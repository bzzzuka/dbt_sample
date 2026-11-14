# Модуль 01 — инфраструктура Docker Compose (Trino)

**Файлы:** `docker-compose.yml`, `.env`, `.gitignore`, `scripts/windows`, `scripts/linux`.

---

## 1. Сервисы

| Сервис | Образ | Роль | Порты |
|---|---|---|---|
| `minio` | coollabsio/minio | S3 | 9000/9001 |
| `data-init` | ./dbt | генерация CSV в S3 (one-shot) | — |
| `spark-etl` | apache/spark:3.5.6 | CSV → Iceberg (one-shot) | — |
| `iceberg-rest` | iceberg-rest-fixture | Iceberg catalog | 8181 |
| `trino` | trinodb/trino:484 | SQL-движок | 8081→8080 |
| `dbt` | ./dbt | dbt-trino run/test (one-shot) | — |
| `superset` | ./superset | BI | 8088 |
| `superset-init` | ./superset | Trino connection (one-shot) | — |
| `superset-worker` | ./superset | Celery worker | — |
| `superset-dashboards` | ./superset | дашборды (one-shot) | — |
| `postgres-airflow` | postgres:15-alpine | Airflow metadata | — |
| `redis` | redis:7-alpine | Celery + Superset results | 6379 |
| `airflow-init` | ./airflow | миграции + admin (one-shot) | — |
| `airflow-webserver` | dbt_sample-airflow | Airflow UI | 8080 |
| `airflow-scheduler` | dbt_sample-airflow | scheduler | — |
| `airflow-worker` | dbt_sample-airflow | Celery worker + Spark | — |
| `airflow-triggerer` | dbt_sample-airflow | triggerer | — |
| `spark-iceberg` | apache/spark:3.5.6 | Spark UI/manual | 4040 |

StarRocks удалён полностью.

---

## 2. One-shot порядок

```
minio healthy
  -> data-init (CSV)
  -> spark-etl (Iceberg)
  -> dbt (37/19)
  -> superset-init -> superset -> superset-dashboards
  -> airflow-init -> airflow-*
```

One-shot сервисы завершаются `Exited (0)`.

---

## 3. Порты

| Порт | Сервис |
|---|---|
| 8080 | Airflow |
| 8081 | Trino |
| 8088 | Superset |
| 8181 | Iceberg REST |
| 9000/9001 | MinIO |
| 4040 | Spark UI |

Порты 8030/9030/8040 (StarRocks) больше не используются.

---

## 4. Volumes

| Volume | Что хранит |
|---|---|
| `minio_data` | CSV + Iceberg warehouse |
| `iceberg_catalog_data` | metadata Iceberg REST (`/tmp`) |
| `superset_home` | Superset metadata |
| `postgres_airflow_data` | Airflow metadata |

---

## 5. `.env`

```env
MINIO_ENDPOINT=http://minio:9000
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin
MINIO_BUCKET=dbt-bucket

TRINO_HOST=trino
TRINO_PORT=8080
TRINO_USER=trino
TRINO_CATALOG=iceberg
TRINO_SCHEMA=analytics
```

---

## 6. Проверка

```powershell
docker compose config
docker compose ps -a
docker exec trino trino --execute "SHOW TABLES FROM iceberg.analytics"
```

---

## 7. Частые проблемы

| Проблема | Решение |
|---|---|
| Trino пуст | `docker compose run --rm --no-deps spark-etl` |
| Trino unhealthy | `docker compose logs trino` |
| Iceberg metadata потеряны | проверить volume `iceberg_catalog_data`, перезапустить Spark ETL |
| dbt dialect error | заменить StarRocks-функции на Trino |
| порт занят | освободить 8080/8081/8088 |

---

## 8. Связанные документы

- [`05-trino.md`](05-trino.md)
- [`../ARCHITECTURE.md`](../ARCHITECTURE.md)
- [`../RUNBOOK.md`](../RUNBOOK.md)
