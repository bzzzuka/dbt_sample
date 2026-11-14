# Модуль 10 — проверки и тесты (Trino)

**Актуально на:** 2026-11-13

---

## 1. Docker

```powershell
docker compose config --quiet
docker compose ps -a
```

Long-running: `Up`; one-shot: `Exited (0)`.

---

## 2. Trino

```powershell
curl -fsS http://localhost:8081/v1/info
docker exec trino trino --execute "SHOW CATALOGS"
docker exec trino trino --execute "SHOW TABLES FROM iceberg.analytics"
```

Ожидаемо: 26 raw, 26 staging views, 11 marts.

---

## 3. Counts

```sql
SELECT 'raw_suppliers' t, COUNT(*) c FROM iceberg.analytics.raw_suppliers
UNION ALL SELECT 'raw_retail_orders', COUNT(*) FROM iceberg.analytics.raw_retail_orders
UNION ALL SELECT 'raw_retail_order_items', COUNT(*) FROM iceberg.analytics.raw_retail_order_items
UNION ALL SELECT 'mart_supplier_performance', COUNT(*) FROM iceberg.analytics.mart_supplier_performance
UNION ALL SELECT 'mart_retail__sales_by_month', COUNT(*) FROM iceberg.analytics.mart_retail__sales_by_month;
```

| Объект | Строк |
|---|---:|
| `raw_suppliers` | 100 000 |
| `raw_supply_orders` | 100 000 |
| `raw_retail_orders` | 200 000 |
| `raw_retail_order_items` | 379 702 |
| `mart_supplier_performance` | 100 000 |
| `mart_warehouse_activity` | 100 000 |
| `mart_retail__customer_ltv` | 50 000 |
| `mart_retail__sales_by_month` | 13 |

---

## 4. dbt

```powershell
docker compose run --rm --no-deps --entrypoint dbt dbt run `
  --profiles-dir /dbt/profiles --project-dir /dbt/project

docker compose run --rm --no-deps --entrypoint dbt dbt test `
  --profiles-dir /dbt/profiles --project-dir /dbt/project
```

Ожидаемо:

```
Found 37 models, 19 tests, 26 sources
Done. PASS=37 ...
Done. PASS=19 ...
```

---

## 5. Spark ETL

```powershell
docker compose run --rm --no-deps spark-etl
```

Ожидаемо: 15 supply + 11 retail таблиц загружены в Iceberg.

---

## 6. Airflow

```powershell
docker exec airflow_scheduler airflow dags list-import-errors
docker exec airflow_scheduler airflow dags trigger dbt_supply_chain_pipeline
docker exec airflow_scheduler airflow dags list-runs -d dbt_supply_chain_pipeline
```

DAG: `generate -> generate_retail -> spark_etl -> dbt_run -> dbt_test`.

---

## 7. Superset

- http://localhost:8088 → admin/admin;
- connection `Trino Iceberg`;
- 2 дашборда.

---

## 8. DBeaver

```text
Driver:   Trino
JDBC:     jdbc:trino://localhost:8081/iceberg/analytics
User:     trino
Password: (пусто)
```

---

## 9. Быстрый troubleshooting

| Симптом | Действие |
|---|---|
| Trino пуст | `docker compose run --rm --no-deps spark-etl` |
| dbt ERROR | смотреть лог, заменить StarRocks-функции на Trino |
| Superset connection error | пересобрать Superset с `trino[sqlalchemy]` |
| Airflow Spark failed | пересобрать Airflow с `pyspark`/Java |
| порт занят | освободить 8080/8081/8088 |

---

## 10. Связанные документы

- [`05-trino.md`](05-trino.md)
- [`03-dbt.md`](03-dbt.md)
- [`../RUNBOOK.md`](../RUNBOOK.md)
