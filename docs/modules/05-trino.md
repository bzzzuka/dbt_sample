# Модуль 05 — Trino + Iceberg (query layer)

**Файлы модуля:**

- `trino/etc/config.properties`
- `trino/etc/node.properties`
- `trino/etc/jvm.config`
- `trino/etc/catalog/iceberg.properties`
- сервис `trino` в `docker-compose.yml`
- `spark/jobs/etl_all_to_iceberg.py` — загрузка Iceberg
- `project/` — dbt-trino модели

---

## 1. Роль Trino

Trino — распределённый SQL-движок. В проекте он **не хранит данные**:
все таблицы лежат в Iceberg на S3/MinIO, а Trino читает и пишет их через
Iceberg REST catalog.

```
MinIO CSV
  -> Spark
  -> Iceberg (Parquet + metadata) в S3
  -> Iceberg REST catalog
  -> Trino (iceberg catalog)
  -> dbt-trino staging/marts
  -> Superset / DBeaver
```

StarRocks из проекта удалён: Trino полностью заменил OLAP-слой.

---

## 2. Сервис и порты

| Параметр | Значение |
|---|---|
| Образ | `trinodb/trino:484` |
| Архитектуры | `linux/amd64`, `linux/arm64` (Mac без Rosetta) |
| Внутренний порт | `8080` |
| Порт хоста | **8081** (8080 занят Airflow) |
| UI | http://localhost:8081 |
| Каталог | `iceberg` |
| Schema | `analytics` |

Healthcheck: `curl -fsS http://localhost:8080/v1/info`.

---

## 3. Каталог Iceberg

`trino/etc/catalog/iceberg.properties`:

```properties
connector.name=iceberg
iceberg.catalog.type=rest
iceberg.rest-catalog.uri=http://iceberg-rest:8181
iceberg.rest-catalog.warehouse=s3://dbt-bucket/warehouse
iceberg.rest-catalog.security=NONE

fs.s3.enabled=true
s3.endpoint=http://minio:9000
s3.region=us-east-1
s3.path-style-access=true
s3.aws-access-key=minioadmin
s3.aws-secret-key=minioadmin
```

`iceberg-rest-fixture` хранит metadata в SQLite внутри контейнера.
В проекте `/tmp` смонтирован в named volume `iceberg_catalog_data`,
поэтому таблицы переживают пересоздание контейнера.

Для production нужен постоянный каталог: Postgres JDBC или Nessie.

---

## 4. Spark-загрузка

`spark/jobs/etl_all_to_iceberg.py` читает CSV из MinIO и пишет Iceberg:

- `raw_{table}` — 15 supply-chain таблиц;
- `raw_retail_{table}` — 11 retail таблиц.

Запуск вручную:

```powershell
docker compose run --rm --no-deps spark-etl
```

При `docker compose up -d` сервис `spark-etl` выполняется автоматически
после `data-init`.

---

## 5. dbt-trino

Профиль `dbt/profiles/profiles.yml`:

```yaml
type: trino
method: none
user: trino
host: trino
port: 8080
database: iceberg
schema: analytics
```

Материализации:

- staging — `view`;
- marts — `table`, `format='PARQUET'`.

Запуск:

```powershell
docker compose run --rm --no-deps --entrypoint dbt dbt run `
  --profiles-dir /dbt/profiles --project-dir /dbt/project

docker compose run --rm --no-deps --entrypoint dbt dbt test `
  --profiles-dir /dbt/profiles --project-dir /dbt/project
```

Результат: **PASS=37**, тесты **PASS=19**.

---

## 6. DBeaver

| Параметр | Значение |
|---|---|
| Driver | Trino |
| Host | localhost |
| Port | 8081 |
| User | trino |
| Password | (пусто) |
| Catalog | iceberg |
| Schema | analytics |
| JDBC | `jdbc:trino://localhost:8081/iceberg/analytics` |

Примеры:

```sql
SHOW TABLES FROM iceberg.analytics;

SELECT month, orders_count, net_revenue
FROM iceberg.analytics.mart_retail__sales_by_month
ORDER BY month;

SELECT supplier_id, total_purchase_amount
FROM iceberg.analytics.mart_supplier_performance
ORDER BY total_purchase_amount DESC
LIMIT 10;
```

---

## 7. Полезные команды

```powershell
docker exec trino trino --execute "SHOW CATALOGS"
docker exec trino trino --execute "SHOW TABLES FROM iceberg.analytics"
docker exec trino trino --execute "SELECT COUNT(*) FROM iceberg.analytics.raw_suppliers"
```

---

## 8. Ограничения

- Iceberg REST fixture — учебный вариант; для production заменить на
  JDBC/Nessie.
- Trino — compute-слой: без Iceberg-таблиц он ничего не вернёт.
- Тяжёлые агрегации выполняются в Iceberg/Trino, partitioning пока не
  настроен.
- Порт 8080 внутри контейнера, на хосте 8081.

---

## 9. Связанные документы

- [`03-dbt.md`](03-dbt.md)
- [`06-spark-iceberg.md`](06-spark-iceberg.md)
- [`08-superset.md`](08-superset.md)
- [`../ARCHITECTURE.md`](../ARCHITECTURE.md)
- [`../../trino_migration.md`](../../trino_migration.md)
