# Модуль 05 — StarRocks (OLAP DWH)

**Файлы модуля:**

- сервис `starrocks` в `docker-compose.yml`
- `dbt/scripts/load_s3_to_starrocks.py`
- `dbt/scripts/load_retail_to_starrocks.py`
- `spark/init-starrocks.sql`
- dbt-модели в `project/models/`

---

## 1. Роль StarRocks

StarRocks — OLAP-база, в которой живут:

- `analytics.raw_*` — сырые supply-chain данные;
- `analytics.raw_retail_*` — сырые retail-данные;
- `analytics.stg_*` / `stg_retail__*` — dbt views;
- `analytics.mart_*` / `mart_retail__*` — dbt tables;
- external catalog `iceberg_lakehouse` — чтение Iceberg из MinIO.

StarRocks использует MySQL-протокол, поэтому к нему можно подключаться
через `mysql` CLI, DBeaver, Python/pymysql и Superset.

---

## 2. Запуск и порты

Образ: `starrocks/allin1-ubuntu:3.4-latest`.  
FE и BE находятся в одном контейнере.

| Порт | Назначение |
|---|---|
| 8030 | FE HTTP UI |
| 9030 | MySQL-протокол (SQL) |
| 8040 | BE HTTP |

Healthcheck в образе отсутствует — это известное ограничение. В compose
используется `condition: service_started`, а Python-загрузчики сами ждут
готовности через `SHOW BACKENDS`.

Проверить:

```powershell
docker compose ps starrocks
docker exec starrocks mysql -h 127.0.0.1 -P 9030 -uroot -e "SELECT 1;"
```

---

## 3. Подключение

| Параметр | Значение |
|---|---|
| Host (с хоста) | `localhost` |
| Port | `9030` |
| User | `root` |
| Password | пусто |
| Database | `analytics` |
| Catalog | `default_catalog` |

Внутри Docker-сети: `starrocks:9030`.

DBeaver: тип подключения **MySQL**.

---

## 4. Слои данных

### 4.1. Raw supply chain

Создаются `load_s3_to_starrocks.py`:

```
raw_suppliers
raw_supply_contracts
raw_supply_orders
raw_supply_items
raw_shipments
raw_warehouses
raw_deliveries
raw_invoices
raw_payments
raw_quality_checks
raw_returns
raw_inventory_movements
raw_transport_routes
raw_customs_declarations
raw_supplier_ratings
raw_moex_prices        # пустая/совместимая таблица для MOEX-модели
```

### 4.2. Raw retail

Создаются `load_retail_to_starrocks.py`:

```
raw_retail_categories
raw_retail_products
raw_retail_customers
raw_retail_stores
raw_retail_promotions
raw_retail_orders
raw_retail_order_items
raw_retail_payments
raw_retail_shipments
raw_retail_returns
raw_retail_reviews
```

### 4.3. Staging и marts

dbt создаёт:

- `stg_*` и `stg_retail__*` — views;
- `mart_*` и `mart_retail__*` — tables.

Список моделей — в [`03-dbt.md`](03-dbt.md).

---

## 5. Как данные попадают в StarRocks

### 5.1. Supply chain

`load_s3_to_starrocks.py`:

1. ждёт `SHOW BACKENDS` (до 240 секунд);
2. `CREATE DATABASE IF NOT EXISTS analytics`;
3. для каждой таблицы:
   - `DROP TABLE IF EXISTS raw_{table}`;
   - `CREATE TABLE ... ENGINE=OLAP DUPLICATE KEY(...) DISTRIBUTED BY HASH(...) BUCKETS 4 PROPERTIES ("replication_num"="1")`;
4. `INSERT INTO raw_{table} SELECT * FROM FILES(...)`;
5. `SELECT COUNT(*)`.

`FILES()` читает CSV напрямую из MinIO:

```sql
INSERT INTO raw_suppliers
SELECT * FROM FILES(
  "path" = "s3://dbt-bucket/stg/suppliers/2026-11-08/suppliers_part_001.csv",
  "format" = "csv",
  "csv.column_separator" = ",",
  "csv.row_delimiter" = "\n",
  "csv.skip_header" = "1",
  "aws.s3.endpoint" = "http://minio:9000",
  "aws.s3.access_key" = "minioadmin",
  "aws.s3.secret_key" = "minioadmin",
  "aws.s3.region" = "us-east-1",
  "aws.s3.enable_ssl" = "false",
  "aws.s3.enable_path_style_access" = "true"
);
```

Загрузка идёт **по одному файлу**, а не wildcard: это стабильнее.

### 5.2. Retail

`load_retail_to_starrocks.py` читает `/tmp/_retail_schema.json` и делает то
же самое для `raw_retail_*`.

---

## 6. External catalog Iceberg

Файл: `spark/init-starrocks.sql`.

```sql
CREATE EXTERNAL CATALOG IF NOT EXISTS iceberg_lakehouse
PROPERTIES (
  "type" = "iceberg",
  "iceberg.catalog.type" = "rest",
  "iceberg.catalog.uri" = "http://iceberg-rest:8181",
  "aws.s3.endpoint" = "http://minio:9000",
  "aws.s3.access_key" = "minioadmin",
  "aws.s3.secret_key" = "minioadmin",
  "aws.s3.enable_path_style_access" = "true",
  "aws.s3.enable_ssl" = "false"
);
```

Применить:

```powershell
Get-Content -Raw spark\init-starrocks.sql | docker exec -i starrocks mysql `
  -h 127.0.0.1 -P 9030 -uroot
```

Проверить:

```sql
SHOW CATALOGS;
SHOW DATABASES FROM iceberg_lakehouse;
SHOW TABLES FROM iceberg_lakehouse.supply_chain;
SELECT COUNT(*) FROM iceberg_lakehouse.supply_chain.suppliers;
```

StarRocks не копирует Iceberg-данные: он читает Parquet из MinIO через
REST-каталог.

---

## 7. Полезные запросы

```sql
USE analytics;

SHOW TABLES;
SHOW TABLES LIKE 'raw_retail_%';
SHOW TABLES LIKE 'mart_retail_%';

SELECT COUNT(*) FROM raw_suppliers;
SELECT COUNT(*) FROM raw_retail_orders;
SELECT COUNT(*) FROM mart_retail__sales_by_month;

SELECT * FROM mart_retail__top_products
ORDER BY revenue DESC
LIMIT 10;

SELECT month, net_revenue, orders_count
FROM mart_retail__sales_by_month
ORDER BY month;
```

---

## 8. Ожидаемые цифры

| Таблица | Строк |
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
| `iceberg_lakehouse.supply_chain.suppliers` | 5000 |

---

## 9. Ограничения и предостережения

- **Нет healthcheck** — не считайте `service_started` ошибкой.
- `DROP TABLE IF EXISTS raw_*` при каждом `data-init` — данные raw
  пересоздаются. dbt-витрины тоже пересоздаются.
- dbt-модели `mart_*` — table, поэтому при `dbt run` они пересобираются.
- StarRocks хранит данные в volume `starrocks_data`.
- External catalog сохраняется в volume, но Iceberg REST metadata — нет
  (см. [`06-spark-iceberg.md`](06-spark-iceberg.md)).
- Для production нужны реплики, партиционирование, TTL и мониторинг; здесь
  учебный single-node.

---

## 10. Частые ошибки

| Ошибка | Причина | Решение |
|---|---|---|
| `Cluster has no available capacity` | FE/BE не готовы | подождать, проверить BE |
| `scheme is null` в `FILES()` | неверный path/endpoint | path-style, один файл |
| `Access denied` | неверные credentials | `.env` и DAG ENV |
| `Table not found` | loader не запускался | `data-init` |
| `Column is ambiguous` | JOIN без алиасов | `ON a.col = b.col` |
| `Insert has filtered data` | пустые/неверные значения | `COALESCE`, проверить CSV |
| StarRocks не видит Iceberg | каталог не создан или REST пуст | `init-starrocks.sql` + Spark ETL |
| `REFRESH EXTERNAL TABLE` нужен | кэш метаданных | выполнить refresh |
| Порт 9030 занят | другой MySQL/StarRocks | остановить конфликтующий процесс |

---

## 11. Связанные документы

- [`03-dbt.md`](03-dbt.md)
- [`04-data-generation.md`](04-data-generation.md)
- [`06-spark-iceberg.md`](06-spark-iceberg.md)
- [`08-superset.md`](08-superset.md)
