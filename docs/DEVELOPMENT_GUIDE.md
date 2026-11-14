# DEVELOPMENT GUIDE — развитие проекта (Trino + Iceberg)

**Актуально на:** 2026-11-13

---

## 1. Архитектура, которую нельзя ломать

```
CSV в MinIO -> Spark -> Iceberg -> Trino -> dbt-trino -> Superset
```

- Trino **не хранит** данные;
- все raw/staging/marts — Iceberg;
- StarRocks удалён, не возвращайте его;
- один каталог `iceberg`, одна schema `analytics`.

---

## 2. Куда что добавлять

| Задача | Файл |
|---|---|
| Supply-таблица | `dbt/scripts/generate_and_upload.py` |
| Новое направление | новый генератор + Spark job + dbt folder |
| Iceberg загрузка | `spark/jobs/etl_all_to_iceberg.py` |
| Staging-модель | `project/models/staging/` |
| Mart | `project/models/marts/` |
| Тесты | `schema.yml` |
| DAG | `airflow/dags/dbt_supply_chain_dag.py` |
| Trino config | `trino/etc/catalog/iceberg.properties` |
| Dashboard | `superset/init/create_all_dashboards.py` |

---

## 3. Добавить supply-таблицу

1. Добавьте таблицу в `TABLES` в `generate_and_upload.py`.
2. Добавьте Spark-таблицу в `SUPPLY_TABLES` в `spark/jobs/etl_all_to_iceberg.py`.
3. `data-init` создаст CSV и `stg_*.sql`.
4. Запустите:

```powershell
docker compose run --rm --no-deps spark-etl
docker compose run --rm --no-deps --entrypoint dbt dbt run `
  --profiles-dir /dbt/profiles --project-dir /dbt/project
```

---

## 4. Добавить mart

```sql
{{ config(materialized='table', format='PARQUET') }}

SELECT ...
FROM {{ ref('stg_retail__orders') }}
```

Требования Trino:

- `materialized='table'`, `format='PARQUET'`;
- никаких `engine`, `keys`, `distributed_by`, `buckets`, `properties`;
- `date_trunc`, `date_diff`, `cast` вместо StarRocks-функций;
- `JOIN ... ON` вместо `USING` при qualified-колонках.

Проверка:

```powershell
docker compose run --rm --no-deps --entrypoint dbt dbt run `
  --profiles-dir /dbt/profiles --project-dir /dbt/project `
  --select +mart_retail__sales_by_month
```

---

## 5. Новое направление

1. Генератор `generate_<domain>.py` (seed, FK, S3 prefix).
2. Добавить таблицы в `spark/jobs/etl_all_to_iceberg.py` (или отдельный job).
3. Iceberg: `lakehouse.analytics.raw_<domain>_*`.
4. dbt: `project/models/staging/<domain>/`, `project/models/marts/<domain>/`.
5. Airflow: задача `spark_etl_to_iceberg` уже общая; dbt подхватит модели.
6. Superset: datasets/charts/dashboards.
7. Docs.

---

## 6. Добавить Spark job

```python
df = spark.read.option("header", "true").option("inferSchema", "true") \
    .csv("s3a://dbt-bucket/<prefix>/{table}/*/*.csv")
df.writeTo("lakehouse.analytics.raw_<table>").createOrReplace()
```

Правила:

- `createOrReplace` для идемпотентности;
- namespace `lakehouse.analytics`;
- явные схемы, если inferSchema даёт неверные типы.

---

## 7. Airflow

DAG: `generate_and_upload -> generate_retail -> spark_etl_to_iceberg ->
dbt_run -> dbt_test`.

Airflow-образ содержит:

- `dbt-trino==1.6.2`;
- `pyspark==3.5.6`;
- Java 17.

Spark запускается в `local[2]` с `--properties-file
/opt/airflow/spark/conf/spark-defaults.conf`.

Проверка:

```powershell
docker exec airflow_scheduler airflow dags list-import-errors
docker exec airflow_scheduler airflow dags trigger dbt_supply_chain_pipeline
```

---

## 8. Тестирование

```powershell
docker compose run --rm --no-deps --entrypoint dbt dbt run `
  --profiles-dir /dbt/profiles --project-dir /dbt/project

docker compose run --rm --no-deps --entrypoint dbt dbt test `
  --profiles-dir /dbt/profiles --project-dir /dbt/project
```

Проверка Trino:

```sql
SELECT COUNT(*) FROM iceberg.analytics.mart_supplier_performance;
```

---

## 9. Git и артефакты

Не коммитить: `target/`, `logs/`, `__pycache__/`, `.user.yml`,
`airflow/logs`, `project/logs`, `project/target`.

`.gitignore` уже настроен.

---

## 10. Версии

| Компонент | Версия |
|---|---|
| Trino | 484 |
| dbt-core | 1.6.2 |
| dbt-trino | 1.6.2 |
| Spark | 3.5.6 |
| Iceberg | 1.4.3 (Spark), REST fixture 1.10.1 |
| Superset | 4.1.2 |
| Airflow | 2.10.5 |

---

## 11. Roadmap

- постоянный Iceberg catalog (Postgres JDBC/Nessie);
- партиционирование Iceberg по датам;
- incremental MERGE;
- больше marts и dashboards;
- мониторинг и CI/CD.

---

## 12. Чек-лист PR

- [ ] `docker compose config` без ошибок;
- [ ] `spark-etl` завершился;
- [ ] dbt run/test PASS;
- [ ] Trino видит таблицы;
- [ ] Superset дашборды открываются;
- [ ] нет StarRocks-кода;
- [ ] docs обновлены.
