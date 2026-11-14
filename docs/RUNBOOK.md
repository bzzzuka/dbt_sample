# RUNBOOK — Trino + Iceberg

**Актуально на:** 2026-11-13

---

## 1. Полный запуск

```powershell
docker compose config
docker compose up -d --build
docker compose ps -a
```

> Первый запуск — **20–30 минут** (100k/200k генерация + Spark ETL).

Порядок one-shot сервисов:

```
data-init   -> CSV в MinIO
spark-etl   -> CSV в Iceberg
dbt         -> 37 моделей, 19 тестов
superset-init -> Trino connection
superset-dashboards -> 2 dashboards
airflow-init -> admin
```

Ожидаемо у long-running сервисов `Up`; у one-shot — `Exited (0)`.

---

## 2. Доступы

| Сервис | URL / порт | Логин / пароль |
|---|---|---|
| Trino | localhost:8081, catalog `iceberg`, schema `analytics` | trino / (пусто) |
| Airflow | http://localhost:8080 | admin / admin |
| Superset | http://localhost:8088 | admin / admin |
| MinIO | http://localhost:9001 | minioadmin / minioadmin |
| Trino UI | http://localhost:8081 | — |
| Iceberg REST | http://localhost:8181 | — |

DBeaver:

```text
Driver: Trino
JDBC:   jdbc:trino://localhost:8081/iceberg/analytics
```

---

## 3. Проверка Trino

```powershell
docker exec trino trino --execute "SHOW CATALOGS"
docker exec trino trino --execute "SHOW TABLES FROM iceberg.analytics"
docker exec trino trino --execute "SELECT COUNT(*) FROM iceberg.analytics.raw_suppliers"
```

Ожидаемо: 26 raw-таблиц, 26 staging views, 11 marts.

---

## 4. dbt

```powershell
docker compose run --rm --no-deps --entrypoint dbt dbt run `
  --profiles-dir /dbt/profiles --project-dir /dbt/project

docker compose run --rm --no-deps --entrypoint dbt dbt test `
  --profiles-dir /dbt/profiles --project-dir /dbt/project
```

Ожидаемо: `PASS=37`, тесты `PASS=19`.

Выборочно:

```powershell
docker compose run --rm --no-deps --entrypoint dbt dbt run `
  --profiles-dir /dbt/profiles --project-dir /dbt/project `
  --select mart_supplier_performance mart_retail__sales_by_month
```

> В dbt 1.6 опции `--profiles-dir` и `--project-dir` ставятся после `run`.

---

## 5. Spark ETL

```powershell
docker compose run --rm --no-deps spark-etl
```

Сервис читает CSV из MinIO и пишет Iceberg `lakehouse.analytics.*`.

При полном `docker compose up -d` `spark-etl` запускается автоматически
после `data-init`.

---

## 6. Airflow DAG

```powershell
docker exec airflow_scheduler airflow dags list
docker exec airflow_scheduler airflow dags list-import-errors
docker exec airflow_scheduler airflow dags unpause dbt_supply_chain_pipeline
docker exec airflow_scheduler airflow dags trigger dbt_supply_chain_pipeline
docker exec airflow_scheduler airflow dags list-runs -d dbt_supply_chain_pipeline
```

DAG: `generate_and_upload -> generate_retail -> spark_etl_to_iceberg ->
dbt_run -> dbt_test`.

---

## 7. Superset

- http://localhost:8088, `admin/admin`;
- connection `Trino Iceberg`;
- дашборды `Supply Chain Overview`, `Retail Overview`.

Проверка SQL Lab:

```sql
SELECT COUNT(*) FROM analytics.mart_supplier_performance;
SELECT COUNT(*) FROM analytics.mart_retail__sales_by_month;
```

---

## 8. Остановка

```powershell
docker compose stop
# или
docker compose down          # volumes сохраняются
docker compose down -v       # полный сброс, данные удаляются
```

---

## 9. Troubleshooting

| Симптом | Причина | Решение |
|---|---|---|
| Trino пустой: нет таблиц | Iceberg REST потерял metadata | `docker compose run --rm --no-deps spark-etl` |
| Trino не видит таблицы после restart | нет volume `iceberg_catalog_data` | проверить volume, перезапустить Spark ETL |
| dbt `FUNCTION_NOT_FOUND` | StarRocks-функция в SQL | заменить на Trino-аналог (`date_diff`, `date_trunc`) |
| dbt `COLUMN_NOT_FOUND` | `USING`/алиасы в Trino | заменить на `ON` |
| Superset connection error | нет `trino[sqlalchemy]` | пересобрать Superset |
| Airflow task упал на Spark | нет Java/pyspark | пересобрать Airflow образ |
| Порт 8081 занят | конфликт | освободить порт |
| `Exited (1)` | ошибка шага | `docker compose logs <service>` |

---

## 10. Чего больше нет

StarRocks удалён: нет портов 8030/9030/8040, нет `starrocks_data`,
нет `dbt-starrocks`, нет `FILES()`, нет external catalog
`iceberg_lakehouse`.

---

## 11. Связанные документы

- [`ARCHITECTURE.md`](ARCHITECTURE.md)
- [`modules/05-trino.md`](modules/05-trino.md)
- [`modules/10-checks-and-tests.md`](modules/10-checks-and-tests.md)
- [`../trino_migration.md`](../trino_migration.md)
