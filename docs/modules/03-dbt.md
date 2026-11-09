# Модуль 03 — dbt (трансформации)

**Файлы модуля:**

- `dbt/Dockerfile`
- `dbt/profiles/profiles.yml`
- `dbt/scripts/init.sh`
- `dbt/scripts/run_dbt.sh`
- `dbt/scripts/generate_and_upload.py`
- `dbt/scripts/load_s3_to_starrocks.py`
- `dbt/scripts/generate_retail.py`
- `dbt/scripts/load_retail_to_starrocks.py`
- `project/dbt_project.yml`
- `project/models/staging/**`
- `project/models/marts/**`

---

## 1. Роль модуля

dbt превращает «сырые» таблицы StarRocks в аналитические витрины:

```
raw_*  ->  stg_* (view)  ->  mart_* (table)
```

- `raw_*` создают Python-загрузчики, не dbt.
- `stg_*` — тонкий слой: в текущем проекте это `SELECT *` из source.
- `mart_*` — агрегаты и бизнес-логика для Superset.

---

## 2. Образ dbt

Файл: `dbt/Dockerfile`.

База: `python:3.11-slim`.

Устанавливается:

- `dbt-core==1.6.2`;
- `dbt-starrocks==1.6.2`;
- `pymysql`, `boto3`, `pandas`, `requests`;
- `mysql-connector-python==8.0.33` принудительно.

Системные пакеты: `git`, `curl`, `default-mysql-client`.

Внутри образа:

- `/dbt/profiles/profiles.yml`;
- `/dbt/scripts/` — скрипты;
- `/dbt/project` — пустая папка; в compose туда монтируется `./project`.

`CMD ["bash"]`.

---

## 3. Профиль dbt

Файл: `dbt/profiles/profiles.yml`.

```yaml
default:
  target: dev
  outputs:
    dev:
      type: starrocks
      host: "{{ env_var('STARROCKS_HOST', 'starrocks') }}"
      port: "{{ env_var('STARROCKS_PORT', '9030') | int }}"
      schema: "{{ env_var('STARROCKS_SCHEMA', 'analytics') }}"
      username: "{{ env_var('STARROCKS_USER', 'root') }}"
      password: "{{ env_var('STARROCKS_PASSWORD', '') }}"
      catalog: "{{ env_var('STARROCKS_CATALOG', 'default_catalog') }}"
      version: "3.4.0"
```

Важно:

- `use_pure` **не используется** — он не поддерживается dbt-starrocks 1.6.2
  и ранее ломал подключение.
- Параметры берутся из env, поэтому `.env`/DAG `ENV` должны быть корректны.

---

## 4. dbt-проект

### 4.1. `project/dbt_project.yml`

```yaml
name: 'my_dbt_project'
version: '1.0.0'
profile: 'default'
model-paths: ["models"]
target-path: "target"
models:
  my_dbt_project:
    staging:
      +materialized: view
    marts:
      +materialized: table
```

### 4.2. Слои

| Папка | Слой | Материализация |
|---|---|---|
| `project/models/staging/` | supply chain staging | view |
| `project/models/staging/retail/` | retail staging | view |
| `project/models/marts/` | supply chain marts | table |
| `project/models/marts/retail/` | retail marts | table |

### 4.3. Sources

Supply chain: `project/models/staging/sources.yml`

```yaml
sources:
  - name: raw
    schema: analytics
    tables:
      - name: raw_suppliers
      ...
      - name: raw_moex_prices
```

Retail: `project/models/staging/retail/sources.yml`

```yaml
sources:
  - name: retail_raw
    schema: analytics
    tables:
      - name: raw_retail_customers
      - name: raw_retail_orders
      ...
```

---

## 5. Модели: фактический состав

### 5.1. Supply chain staging (15)

```
stg_suppliers
stg_supply_contracts
stg_supply_orders
stg_supply_items
stg_shipments
stg_warehouses
stg_deliveries
stg_invoices
stg_payments
stg_quality_checks
stg_returns
stg_inventory_movements
stg_transport_routes
stg_customs_declarations
stg_supplier_ratings
```

Файлы: `project/models/staging/stg_*.sql`.  
Важно: эти файлы **перегенерируются** скриптом
`generate_and_upload.py` при каждом `data-init`. Не храните в них ручные
правки — они будут перезаписаны.

### 5.2. MOEX staging (опционально, 1)

```
stg_moex_prices
```

Файл: `project/models/staging/stg_moex_prices.sql`.  
Это отдельная экспериментальная ветка, не входит в основной DAG. В
`sources.yml` есть `raw_moex_prices`; загрузчик создаёт пустую таблицу, если
данных MOEX нет.

### 5.3. Retail staging (11)

```
stg_retail__categories
stg_retail__products
stg_retail__customers
stg_retail__stores
stg_retail__promotions
stg_retail__orders
stg_retail__order_items
stg_retail__payments
stg_retail__shipments
stg_retail__returns
stg_retail__reviews
```

Файлы: `project/models/staging/retail/stg_retail__*.sql`.

### 5.4. Supply chain marts (6)

| Модель | Что содержит |
|---|---|
| `mart_supplier_performance` | KPI поставщиков: заказы, суммы, контракты, рейтинг |
| `mart_supply_by_category` | Выручка и количество по категориям |
| `mart_delivery_kpi` | Сроки, стоимость, статусы доставок |
| `mart_warehouse_activity` | Движения и доставки по складам |
| `mart_payment_summary` | Инвойсы и платежи по месяцам/валютам |
| `mart_transport_analysis` | Маршруты и стоимость по видам транспорта |

Файлы: `project/models/marts/mart_*.sql`.

### 5.5. MOEX mart (опционально, 1)

`mart_moex_daily_returns` — производная от `stg_moex_prices`.

### 5.6. Retail marts (5)

| Модель | Что содержит |
|---|---|
| `mart_retail__sales_by_month` | Выручка, заказы, скидки, средний чек по месяцам |
| `mart_retail__top_products` | Топ товаров по выручке и units |
| `mart_retail__customer_ltv` | LTV, частота, первый/последний заказ |
| `mart_retail__returns_rate` | Доля и сумма возвратов по месяцам |
| `mart_retail__sales_by_category` | Продажи и доля по категориям |

Файлы: `project/models/marts/retail/mart_retail__*.sql`.

### 5.7. Итоговые цифры

```
39 models = 15 supply chain stg + 1 MOEX stg + 11 retail stg
          + 6 supply chain marts + 1 MOEX mart + 5 retail marts
19 tests  = 9 supply chain + 10 retail
27 sources = 16 supply chain (15 + MOEX) + 11 retail
```

---

## 6. Тесты

`project/models/marts/schema.yml`:

- `mart_supplier_performance.supplier_id` — unique/not_null;
- `mart_supplier_performance.supplier_name` — not_null;
- `mart_supply_by_category.category` — unique/not_null;
- `mart_warehouse_activity.warehouse_id` — unique/not_null;
- `mart_transport_analysis.transport_mode` — unique/not_null.

`project/models/marts/retail/schema.yml`:

- `mart_retail__sales_by_month.month` — unique/not_null;
- `mart_retail__top_products.product_id` — unique/not_null;
- `mart_retail__customer_ltv.customer_id` — unique/not_null;
- `mart_retail__returns_rate.month` — unique/not_null;
- `mart_retail__sales_by_category.category_id` — unique/not_null.

Итого 19 тестов.

---

## 7. Как запускается dbt

### 7.1. В `data-init` и `dbt` сервисе

`dbt/scripts/init.sh`:

1. supply chain generation → S3;
2. supply chain load → StarRocks;
3. retail generation → S3;
4. retail load → StarRocks.

`dbt/scripts/run_dbt.sh`:

```bash
cd /dbt/project
dbt debug
dbt run
dbt test
```

`dbt`-сервис — one-shot. После завершения смотрите:

```powershell
docker compose logs dbt --tail 100
```

### 7.2. В Airflow

Задачи `dbt_run` и `dbt_test` выполняют dbt внутри Airflow worker:

```bash
cd /opt/airflow/dbt_project
dbt --log-path /tmp/dbt_logs run \
  --profiles-dir /opt/airflow/dbt_profiles \
  --target-path /tmp/dbt_target
```

### 7.3. Вручную

```powershell
docker compose run --rm --no-deps --entrypoint dbt dbt `
  --profiles-dir /dbt/profiles debug

docker compose run --rm --no-deps --entrypoint dbt dbt `
  --profiles-dir /dbt/profiles run

docker compose run --rm --no-deps --entrypoint dbt dbt `
  --profiles-dir /dbt/profiles test
```

Выборочно:

```powershell
# только retail staging
docker compose run --rm --no-deps --entrypoint dbt dbt `
  --profiles-dir /dbt/profiles run --select "stg_retail__*"

# только retail marts
docker compose run --rm --no-deps --entrypoint dbt dbt `
  --profiles-dir /dbt/profiles run --select "mart_retail__*"

# одна модель и её зависимости
docker compose run --rm --no-deps --entrypoint dbt dbt `
  --profiles-dir /dbt/profiles run --select "+mart_retail__sales_by_month"
```

> `--entrypoint dbt` обязателен. Без него запускается
> `/dbt/scripts/run_dbt.sh` и аргументы игнорируются.

---

## 8. Как добавить модель

1. Staging:
   - добавьте source в `sources.yml`;
   - создайте `stg_*.sql` с `{{ source(...) }}`;
   - для retail используйте отдельную папку `staging/retail/`.
2. Mart:
   - создайте `mart_*.sql` с `{{ ref(...) }}`;
   - укажите `materialized='table'` и StarRocks-параметры;
   - добавьте тесты в `schema.yml`.
3. Запустите `dbt run --select ...` и `dbt test`.

Подробный рецепт — в [`../DEVELOPMENT_GUIDE.md`](../DEVELOPMENT_GUIDE.md).

---

## 9. Важные предупреждения

### 9.1. Генератор перезаписывает staging supply chain

`generate_and_upload.py` при каждом запуске:

- перезаписывает `project/models/staging/stg_*.sql` для 15 supply-chain
  таблиц;
- перезаписывает `project/models/staging/sources.yml`.

Поэтому:

- не редактируйте эти 15 файлов вручную;
- свои модели кладите в отдельные файлы/папки;
- если нужно изменить генерацию — правьте генератор.

### 9.2. Не запускайте `setup_starrocks.py`

Этот legacy-генератор перезапишет `docker-compose.yml`, `dbt/Dockerfile`,
`profiles.yml`, `init.sh`, `load_s3_to_starrocks.py`, модели и `sources.yml`
старой версией (dbt 1.9.0, FE/BE split, без retail). Это сломает проект.
Подробнее — [`09-scripts-and-legacy.md`](09-scripts-and-legacy.md).

### 9.3. dbt-starrocks 1.6.2

Не обновляйте до 1.7+ без проверки:

- `use_pure` не поддерживается;
- `properties` в конфиге модели должен быть **строкой JSON**, а не dict;
- `mysql-connector-python==8.0.33` установлен принудительно.

---

## 10. Частые ошибки

| Ошибка | Причина | Решение |
|---|---|---|
| `dbt: command not found` | PATH | использовать образ dbt/Airflow, не хост |
| `Database Error: Access denied` | неверный user/password | проверить `profiles.yml` и `.env` |
| `properties JSON error` | dict вместо строки | `properties='{"replication_num": "1"}'` |
| `use_pure is not supported` | старый параметр | удалить `use_pure` |
| `Compilation Error: model not found` | нет `ref`/`source` | проверить имена и `sources.yml` |
| `dbt run` падает на модели | нет raw-таблицы | сначала `data-init`/загрузчик |
| `PASS=... ERROR=1` | SQL/тест | смотреть `dbt.log`, запустить модель отдельно |
| `PermissionError` | запись в read-only | `--log-path /tmp`, `--target-path /tmp` |

---

## 11. Связанные документы

- [`04-data-generation.md`](04-data-generation.md)
- [`05-starrocks.md`](05-starrocks.md)
- [`02-airflow.md`](02-airflow.md)
- [`../DEVELOPMENT_GUIDE.md`](../DEVELOPMENT_GUIDE.md)
