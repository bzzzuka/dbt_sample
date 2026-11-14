# Модуль 04 — генерация данных

**Файлы:**

- `dbt/scripts/generate_and_upload.py` — supply chain
- `dbt/scripts/generate_retail.py` — retail
- `spark/jobs/etl_all_to_iceberg.py` — загрузка всех CSV в Iceberg

---

## 1. Роль

Генераторы создают CSV в MinIO; Spark переносит их в Iceberg; dbt строит
модели. StarRocks-загрузчиков больше нет.

```
generate_*.py -> s3://dbt-bucket/{stg|retail/stg}/... -> Spark -> Iceberg
```

---

## 2. Supply chain

15 таблиц, до 123 колонок. В текущем окружении — 100 000 строк/таблицу.

Переменные: `ROWS`, `CHUNK_SIZE`, `COLUMNS_PER_TABLE`, `LAYER`,
`PARTITION_DATE`, `CLEAN_BEFORE_UPLOAD`.

Генератор также перезаписывает:

- `project/models/staging/stg_*.sql` (15);
- `project/models/staging/sources.yml`.

Не редактируйте эти 15 файлов вручную.

---

## 3. Retail

11 таблиц. В текущем окружении:

| Таблица | Строк |
|---|---:|
| categories | 20 |
| products | 2 000 |
| customers | 50 000 |
| stores | 200 |
| promotions | 101 |
| orders | 200 000 |
| order_items | 379 702 |
| payments | 200 000 |
| shipments | 164 010 |
| returns | 11 676 |
| reviews | 20 000 |

Переменные: `RETAIL_ORDERS`, `RETAIL_CUSTOMERS`, `RETAIL_PRODUCTS`,
`RETAIL_STORES`, `RETAIL_PROMOTIONS`, `RETAIL_REVIEWS`.

---

## 4. Spark-загрузка

`spark/jobs/etl_all_to_iceberg.py`:

- читает `s3a://dbt-bucket/stg/{table}/*/*.csv`;
- читает `s3a://dbt-bucket/retail/stg/{table}/*/*.csv`;
- пишет `lakehouse.analytics.raw_{table}` и `raw_retail_{table}`.

Запуск:

```powershell
docker compose run --rm --no-deps spark-etl
```

При `docker compose up -d` запускается автоматически после `data-init`.

---

## 5. Правила

1. Seed фиксирован — не меняйте без причины.
2. Новые таблицы добавляйте в генератор и в `etl_all_to_iceberg.py`.
3. Объём: 1000–5000 строк по умолчанию, в текущем окружении 100k/200k.
4. После генерации обязательно запускайте Spark ETL и dbt.

---

## 6. Проверка

```sql
SELECT COUNT(*) FROM iceberg.analytics.raw_suppliers;
SELECT COUNT(*) FROM iceberg.analytics.raw_retail_orders;
SELECT COUNT(*) FROM iceberg.analytics.raw_retail_order_items;
```

---

## 7. Связанные документы

- [`03-dbt.md`](03-dbt.md)
- [`05-trino.md`](05-trino.md)
- [`07-minio.md`](07-minio.md)
