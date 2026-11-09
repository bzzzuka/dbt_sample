# Модуль 10 — проверки и тесты

**Актуально на:** 2026-11-09

Этот файл — чек-лист «всё ли работает». Выполняйте сверху вниз после
запуска стека или после изменений.

---

## 1. Docker Compose

```powershell
docker compose config --quiet
docker compose ps -a
```

Ожидаемо:

- конфиг без ошибок;
- long-running сервисы `Up`;
- healthy там, где есть healthcheck;
- one-shot сервисы `Exited (0)`.

Подробная таблица статусов — в [`../RUNBOOK.md`](../RUNBOOK.md).

---

## 2. Health endpoints

```powershell
Invoke-WebRequest -UseBasicParsing http://localhost:8080/health
Invoke-WebRequest -UseBasicParsing http://localhost:8088/health
Invoke-WebRequest -UseBasicParsing http://localhost:8181/v1/config
Invoke-WebRequest -UseBasicParsing http://localhost:9000/minio/health/live
```

Ожидаемо `200`.

---

## 3. MinIO

```powershell
docker exec dbt_minio mc alias set local http://localhost:9000 minioadmin minioadmin
docker exec dbt_minio mc ls local/dbt-bucket
docker exec dbt_minio mc ls --recursive local/dbt-bucket/stg/suppliers
docker exec dbt_minio mc ls --recursive local/dbt-bucket/retail/stg/orders
docker exec dbt_minio mc ls --recursive local/dbt-bucket/warehouse
```

Ожидаемо:

- bucket `dbt-bucket` существует;
- есть CSV supply chain;
- есть CSV retail;
- есть Iceberg warehouse (после Spark ETL).

---

## 4. StarRocks: raw и marts

```powershell
docker exec starrocks mysql -h 127.0.0.1 -P 9030 -uroot -e "USE analytics; SHOW TABLES;"
```

Проверить ключевые таблицы:

```powershell
docker exec starrocks mysql -h 127.0.0.1 -P 9030 -uroot `
  -e "SELECT COUNT(*) AS raw_suppliers FROM analytics.raw_suppliers;"

docker exec starrocks mysql -h 127.0.0.1 -P 9030 -uroot `
  -e "SELECT COUNT(*) AS raw_retail_orders FROM analytics.raw_retail_orders;"

docker exec starrocks mysql -h 127.0.0.1 -P 9030 -uroot `
  -e "SELECT COUNT(*) AS sales_months FROM analytics.mart_retail__sales_by_month;"

docker exec starrocks mysql -h 127.0.0.1 -P 9030 -uroot `
  -e "SELECT COUNT(*) AS supplier_kpi FROM analytics.mart_supplier_performance;"
```

Ожидаемые значения:

| Проверка | Ожидаемо |
|---|---:|
| `raw_suppliers` | 5000 |
| `raw_retail_orders` | 5000 |
| `raw_retail_order_items` | ~9500 |
| `mart_retail__sales_by_month` | 13 |
| `mart_retail__top_products` | 500 |
| `mart_retail__customer_ltv` | 3000 |
| `mart_retail__returns_rate` | 13 |
| `mart_retail__sales_by_category` | 20 |
| `mart_supplier_performance` | 5000 |

---

## 5. dbt

### 5.1. Полный прогон

```powershell
docker compose logs dbt --tail 100
```

Ожидаемо:

```
Found 39 models, 19 tests, 27 sources
Done. PASS=39 WARN=0 ERROR=0 SKIP=0 TOTAL=39
Done. PASS=19 WARN=0 ERROR=0 SKIP=0 TOTAL=19
```

### 5.2. Отдельные селекторы

```powershell
docker compose run --rm --no-deps --entrypoint dbt dbt `
  --profiles-dir /dbt/profiles run --select "stg_retail__*"

docker compose run --rm --no-deps --entrypoint dbt dbt `
  --profiles-dir /dbt/profiles run --select "mart_retail__*"

docker compose run --rm --no-deps --entrypoint dbt dbt `
  --profiles-dir /dbt/profiles test
```

Ожидаемо: staging — 11 моделей, marts — 5, тесты — 19.

### 5.3. dbt debug

```powershell
docker compose run --rm --no-deps --entrypoint dbt dbt `
  --profiles-dir /dbt/profiles debug
```

Ожидаемо: подключение к StarRocks успешно.

---

## 6. Airflow

### 6.1. DAG виден

```powershell
docker exec airflow_scheduler airflow dags list
docker exec airflow_scheduler airflow dags list-import-errors
```

Ожидаемо: `dbt_supply_chain_pipeline`, импорт-ошибок нет.

### 6.2. Запуск

```powershell
docker exec airflow_scheduler airflow dags unpause dbt_supply_chain_pipeline
docker exec airflow_scheduler airflow dags trigger dbt_supply_chain_pipeline
docker exec airflow_scheduler airflow dags list-runs -d dbt_supply_chain_pipeline
```

Ожидаемо: run `success`, 6 задач `success`.

### 6.3. Логин

- http://localhost:8080
- `admin/admin`
- если не работает — [`02-airflow.md`](02-airflow.md), раздел «Авторизация».

---

## 7. Spark + Iceberg

```powershell
docker exec spark_iceberg /opt/spark/bin/spark-submit `
  /opt/spark/jobs/etl_supply_chain.py

docker exec spark_iceberg /opt/spark/bin/spark-submit `
  /opt/spark/jobs/verify_iceberg.py
```

Ожидаемо:

- 5000 строк, 121 колонка;
- namespace `supply_chain`;
- таблица `suppliers`;
- Spark видит данные.

---

## 8. StarRocks external catalog

```powershell
Get-Content -Raw spark\init-starrocks.sql | docker exec -i starrocks mysql `
  -h 127.0.0.1 -P 9030 -uroot

docker exec starrocks mysql -h 127.0.0.1 -P 9030 -uroot -e "SHOW CATALOGS;"
docker exec starrocks mysql -h 127.0.0.1 -P 9030 -uroot -e "SHOW DATABASES FROM iceberg_lakehouse;"
docker exec starrocks mysql -h 127.0.0.1 -P 9030 -uroot -e "SELECT COUNT(*) FROM iceberg_lakehouse.supply_chain.suppliers;"
```

Ожидаемо: `iceberg_lakehouse`, `supply_chain`, `suppliers`, `5000`.

> Если получили `NoSuchNamespaceException`, значит `iceberg-rest` потерял
> метаданные после пересоздания. Повторно запустите Spark ETL.

---

## 9. Superset

### 9.1. UI

- http://localhost:8088
- `admin/admin`
- открыть `Supply Chain Overview`
- открыть `Retail Overview`

### 9.2. API

```powershell
$login = Invoke-RestMethod -Method Post `
  -Uri http://localhost:8088/api/v1/security/login `
  -ContentType 'application/json' `
  -Body '{"username":"admin","password":"admin","provider":"db","refresh":true}'

$h = @{ Authorization = "Bearer $($login.access_token)" }

Invoke-RestMethod -Uri http://localhost:8088/api/v1/dashboard/ -Headers $h |
  Select-Object -ExpandProperty result |
  Select-Object id, dashboard_title, published
```

Ожидаемо: 2 дашборда, `published=True`.

### 9.3. SQL Lab

В UI: SQL Lab → `StarRocks Analytics` → schema `analytics`.

```sql
SELECT COUNT(*) FROM mart_retail__sales_by_month;
SELECT COUNT(*) FROM mart_supplier_performance;
```

Ожидаемо: 13 и 5000.

Если ошибка `Results backend is not configured` — проверьте
`superset_config.py` и Redis.

---

## 10. Полный end-to-end сценарий

```powershell
docker compose up -d --build
Start-Sleep -Seconds 60
docker compose ps -a

# DAG
docker exec airflow_scheduler airflow dags unpause dbt_supply_chain_pipeline
docker exec airflow_scheduler airflow dags trigger dbt_supply_chain_pipeline
Start-Sleep -Seconds 90
docker exec airflow_scheduler airflow dags list-runs -d dbt_supply_chain_pipeline

# StarRocks
docker exec starrocks mysql -h 127.0.0.1 -P 9030 -uroot `
  -e "SELECT COUNT(*) FROM analytics.mart_retail__sales_by_month;"

# Spark / Iceberg
docker exec spark_iceberg /opt/spark/bin/spark-submit `
  /opt/spark/jobs/etl_supply_chain.py

# External catalog
docker exec starrocks mysql -h 127.0.0.1 -P 9030 -uroot `
  -e "SELECT COUNT(*) FROM iceberg_lakehouse.supply_chain.suppliers;"

# Superset
Invoke-WebRequest -UseBasicParsing http://localhost:8088/health
```

---

## 11. Быстрый troubleshooting

| Симптом | Первое действие |
|---|---|
| сервис `Exited (1)` | `docker compose logs <service>` |
| Airflow не пускает | `airflow users list`, `db check`, reset password |
| DAG не виден | `airflow dags list-import-errors` |
| dbt ошибка | `docker compose logs dbt` |
| StarRocks пустой | `docker compose logs data-init` |
| Superset пустой | `docker compose logs superset-dashboards` |
| Iceberg пустой | `etl_supply_chain.py` заново |
| чарт без данных | SQL Lab + `mart_*` counts |
| OOM | `docker stats --no-stream` |

---

## 12. Связанные документы

- [`../RUNBOOK.md`](../RUNBOOK.md)
- [`02-airflow.md`](02-airflow.md)
- [`03-dbt.md`](03-dbt.md)
- [`05-starrocks.md`](05-starrocks.md)
- [`06-spark-iceberg.md`](06-spark-iceberg.md)
- [`08-superset.md`](08-superset.md)
