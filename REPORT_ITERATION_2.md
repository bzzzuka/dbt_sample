# REPORT_ITERATION_2.md — вторая итерация

**Дата:** 2026-11-08  
**Итоговый статус:** **READY**

---

## Краткое резюме

Выполнены три задачи в заданном порядке:

1. **Airflow auth:** вход `admin/admin` на `http://localhost:8080` работает.
   Причина `500` — пароль admin был сохранён в формате `scrypt` (Werkzeug 3.x),
   а Airflow 2.10.5 использует Werkzeug 2.2.3, который не умеет проверять scrypt.
   Пароль сброшен, `AIRFLOW__WEBSERVER__SECRET_KEY` зафиксирован в compose.
2. **Retail data:** добавлены 11 таблиц retail/e-commerce (seed=42), загрузка
   в `s3://dbt-bucket/retail/stg/{table}/{date}/*.csv` и StarRocks `raw_retail_*`,
   11 staging-моделей и 5 mart-витрин. `dbt run` — PASS=39, `dbt test` — PASS=19.
3. **Superset:** созданы идемпотентно 2 дашборда по 8 чартов:
   `Supply Chain Overview` и `Retail Overview`. Чарты отдают непустые данные,
   страницы дашбордов открываются (HTTP 200).

На момент завершения все долгоживущие сервисы подняты. One-shot сервисы
(`airflow-init`, `data-init`, `dbt`, `superset-init`, `superset-dashboards`)
завершились с кодом 0 — это штатное поведение, не «down».

---

## Задача 1. Airflow: вход admin/admin

### 1.1. Исходная диагностика

На старте итерации контейнеры отсутствовали (вероятно, Docker Desktop
перезапускался), образы и volumes сохранились. Стек поднят командой
`docker compose up -d` без удаления volumes.

| Проверка | Результат |
|---|---|
| `docker compose ps` | Airflow webserver/scheduler/worker/triggerer — Up, webserver и worker healthy |
| `GET /health` | `200`, metastore/scheduler/triggerer healthy |
| `GET /login/` | `200`, форма логина и CSRF-токен отдаются |
| `POST /login/` без CSRF | `400`, `The CSRF token is missing.` — ожидаемо |
| `POST /login/` с валидным CSRF | **`500 INTERNAL SERVER ERROR`** |
| `airflow users list` | `admin`, роль `Admin`, active |
| `airflow db check` | `Connection successful` |
| Werkzeug | `2.2.3` |
| Хеш пароля в БД | `scrypt:32768:8:1$...` |

Traceback из `docker compose logs airflow-webserver`:

```
File ".../airflow/providers/fab/auth_manager/security_manager/override.py", line 2217, in auth_user_db
    elif check_password_hash(user.password, password):
File ".../werkzeug/security.py", line 107, in check_password_hash
    return hmac.compare_digest(_hash_internal(method, salt, password)[0], hashval)
...
ValueError: unsupported hash type scrypt:32768:8:1
```

### 1.2. Причина

Пароль `admin` был создан более новым Werkzeug (scrypt). Текущий Airflow 2.10.5
использует Werkzeug 2.2.3, который не поддерживает проверку scrypt.
`400 Bad Request` без CSRF-токена — это отдельное ожидаемое поведение CSRF,
а не причина невозможности входа.

Дополнительно: `AIRFLOW__WEBSERVER__SECRET_KEY` был задан в `.env`, но не
передавался в контейнеры Airflow (нет `env_file` и не было переменной в
`environment`). Airflow генерировал ключ сам; при пересоздании контейнера
ключ менялся и инвалидировал сессии.

### 1.3. Что сделано

1. Сброшен пароль admin под текущий Werkzeug:
   ```powershell
   docker exec airflow_webserver airflow users reset-password --username admin --password admin
   ```
   Новый хеш: `pbkdf2:sha256:260000$...`.
2. Во все Airflow-сервисы (`airflow-init`, webserver, scheduler, worker,
   triggerer) добавлена переменная:
   ```yaml
   - AIRFLOW__WEBSERVER__SECRET_KEY=${AIRFLOW__WEBSERVER__SECRET_KEY}
   ```
3. Из `.env` удалены дубли `AIRFLOW_FERNET_KEY` и
   `AIRFLOW__WEBSERVER__SECRET_KEY`.
4. Учётные данные admin для `airflow-init` вынесены в `.env`
   (`AIRFLOW_ADMIN_USERNAME`, `AIRFLOW_ADMIN_PASSWORD`) вместо хардкода в compose.
5. CSRF **не отключался**.
6. Airflow-контейнеры пересозданы без `docker compose down` и без удаления volumes.

### 1.4. Проверка

```powershell
# CSRF-токен + POST логина
# login_status=302, Location: /home
# GET /home -> 200, title "DAGs - Airflow"
```

| Проверка | Результат |
|---|---|
| `POST /login/` с CSRF | `302 Found`, `Location: /home` |
| `GET /home` | `200`, `DAGs - Airflow`, DAG `dbt_supply_chain_pipeline` виден |
| `airflow_webserver env` | `AIRFLOW__WEBSERVER__SECRET_KEY=airflow_webserver_secret_local` |
| `airflow_scheduler env` | тот же ключ |
| `airflow config get-value webserver secret_key` | `airflow_webserver_secret_local` |
| `airflow config get-value webserver base_url` | `http://localhost:8080` |
| `Fernet(AIRFLOW_FERNET_KEY)` | `fernet OK` (44-char base64) |
| `airflow dags list-import-errors` | `No data found` |

**Итог: работает.** Вход `admin/admin` проверен фактическим POST с CSRF и
переходом на `/home` (HTTP 200).

---

## Задача 2. Retail / e-commerce данные

### 2.1. Новые таблицы

Направление: **retail / e-commerce**. Сгенерировано 11 связанных таблиц.

| Таблица (S3 / raw) | Строк | Ключевые поля |
|---|---:|---|
| `categories` / `raw_retail_categories` | 20 | category_id, category_name, department, is_active |
| `products` / `raw_retail_products` | 500 | product_id, product_name, category_id, brand, unit_price, cost, launch_date |
| `customers` / `raw_retail_customers` | 3000 | customer_id, first/last_name, email, city, country, signup_date, segment, loyalty_tier |
| `stores` / `raw_retail_stores` | 50 | store_id, store_name, city, country, store_type, opened_date |
| `promotions` / `raw_retail_promotions` | 31 | promotion_id (0 = без промо), promotion_name, promo_type, discount_pct, start/end_date |
| `orders` / `raw_retail_orders` | 5000 | order_id, customer_id, store_id, promotion_id, order_date, status, channel, subtotal, discount_amount, shipping_cost, tax_amount, total_amount |
| `order_items` / `raw_retail_order_items` | 9449 | order_item_id, order_id, product_id, quantity, unit_price, discount_pct, line_total |
| `payments` / `raw_retail_payments` | 5000 | payment_id, order_id, payment_date, payment_method, amount, status, transaction_ref |
| `shipments` / `raw_retail_shipments` | 4088 | shipment_id, order_id, carrier, shipping_method, shipped/promised/delivered_date, status, tracking_number |
| `returns` / `raw_retail_returns` | 290 | return_id, order_id, return_date, reason, status, refund_amount |
| `reviews` / `raw_retail_reviews` | 2000 | review_id, product_id, customer_id, order_id, rating, review_date, review_text, helpful_votes |

Связи согласованы: `order_items.order_id → orders`, `order_items.product_id →
products`, `orders.customer_id → customers`, `orders.store_id → stores`,
`orders.promotion_id → promotions` (0 = без промо), `payments.order_id → orders`,
`shipments.order_id → orders`, `returns.order_id → orders`.

### 2.2. Генерация и загрузка

- Файл: `dbt/scripts/generate_retail.py`.
- Seed: `RETAIL_SEED=42` (фиксированный `random.Random(SEED)`).
- Объём по умолчанию: customers=3000, orders=5000, products=500,
  stores=50, promotions=30, reviews=2000.
- S3-путь: `s3://dbt-bucket/retail/stg/{table}/{date}/*.csv`.
  Использован отдельный префикс `retail/stg`, чтобы не пересекаться с
  supply_chain (`stg/...`).
- StarRocks: `analytics.raw_retail_*` (11 таблиц), загрузка через `FILES()`.
- Файл загрузчика: `dbt/scripts/load_retail_to_starrocks.py`.
- Схема для загрузчика: `/tmp/_retail_schema.json`.
- `data-init` (`dbt/scripts/init.sh`) теперь выполняет 4 шага:
  supply_chain → S3 → StarRocks → retail → S3 → StarRocks.

### 2.3. Новые dbt-модели

Staging (11, view):

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

Marts (5, table):

```
mart_retail__sales_by_month
mart_retail__top_products
mart_retail__customer_ltv
mart_retail__returns_rate
mart_retail__sales_by_category
```

Файлы: `project/models/staging/retail/` и
`project/models/marts/retail/`. Источники — `project/models/staging/retail/sources.yml`
(source `retail_raw`). Тесты — `project/models/marts/retail/schema.yml`
(10 тестов unique/not_null).

### 2.4. Результаты dbt

```text
Found 39 models, 19 tests, 27 sources
dbt run:  Done. PASS=39 WARN=0 ERROR=0 SKIP=0 TOTAL=39
dbt test: Done. PASS=19 WARN=0 ERROR=0 SKIP=0 TOTAL=19
```

Контрольные `COUNT(*)`:

| Витрина | Строк |
|---|---:|
| `raw_retail_orders` | 5000 |
| `stg_retail__orders` | 5000 |
| `mart_retail__sales_by_month` | 13 |
| `mart_retail__top_products` | 500 |
| `mart_retail__customer_ltv` | 3000 |
| `mart_retail__returns_rate` | 13 |
| `mart_retail__sales_by_category` | 20 |

### 2.5. Airflow DAG

В `dbt_supply_chain_pipeline` добавлены задачи `generate_retail` и
`load_retail_to_starrocks`. Итоговая цепочка:

```
generate_and_upload
  >> load_to_starrocks
  >> generate_retail
  >> load_retail_to_starrocks
  >> dbt_run
  >> dbt_test
```

Проверочный запуск `manual__2026-11-08T14:02:46+00:00`: **success**,
все 6 задач `success`, включая `generate_retail` и `load_retail_to_starrocks`.

Существующий supply_chain не сломан: `mart_supplier_performance` = 5000 строк,
старые DAG-задачи и модели работают. Iceberg после пересоздания контейнера
восстановлен повторным `etl_supply_chain.py`; StarRocks
`iceberg_lakehouse.supply_chain.suppliers` = 5000 строк.

---

## Задача 3. Superset dashboards

### 3.1. Как созданы

- Скрипт: `superset/init/create_all_dashboards.py`.
- Запуск: one-shot сервис `superset-dashboards` (добавлен в `docker-compose.yml`),
  зависит от `superset: service_healthy` и `redis: service_healthy`.
- Используется Superset REST API 4.1.2:
  `/api/v1/security/login`, `/api/v1/security/csrf_token/`,
  `/api/v1/dataset/`, `/api/v1/chart/`, `/api/v1/dashboard/`.
- Идемпотентность: `find_or_create` по имени для dataset, chart и dashboard.
  Повторные запуски обновляют существующие объекты, а не создают дубликаты.
- Results backend для SQL Lab/чартов: Redis (db 4), задан в
  `superset/superset_config.py` (`RESULTS_BACKEND = RedisCache(...)`).

### 3.2. Дашборды и чарты

**Supply Chain Overview** (dashboard_id=1, 8 chart):

1. SC: Total Purchase Amount — KPI
2. SC: Total Orders — KPI
3. SC: Top-10 Suppliers by Turnover — bar
4. SC: Revenue by Category — pie
5. SC: Payments vs Invoices by Month — line
6. SC: Delivery KPI — table
7. SC: Top-10 Warehouses by Movements — bar
8. SC: Delivery Cost by Transport Mode — bar

**Retail Overview** (dashboard_id=2, 8 chart):

1. RT: Total Revenue — KPI
2. RT: Total Orders — KPI
3. RT: Avg Order Value — KPI
4. RT: Revenue by Month — line
5. RT: Top Products by Revenue — bar
6. RT: Revenue by Category — pie
7. RT: Top Customers by LTV — table
8. RT: Returns Rate by Month — line

Датасеты: 11 (6 supply_chain + 5 retail), все поверх `analytics.mart_*`,
не поверх raw/staging.

### 3.3. Проверка

| Проверка | Результат |
|---|---|
| `GET /superset/dashboard/1/` после логина | `200`, title `Supply Chain Overview` |
| `GET /superset/dashboard/2/` после логина | `200`, title `Retail Overview` |
| `dashboard 2 charts` | 8 |
| `dashboard_slices` для dashboard 2 | 8 записей |
| SQL Lab `mart_supplier_performance` | success, `cnt=5000` |
| SQL Lab `mart_retail__sales_by_month` | success, `cnt=13` |
| SQL Lab `mart_retail__top_products` | success, `cnt=500` |
| SQL Lab `mart_retail__customer_ltv` | success, `cnt=3000` |
| SQL Lab `mart_retail__returns_rate` | success, `cnt=13` |
| SQL Lab `mart_retail__sales_by_category` | success, `cnt=20` |
| Chart data API, `RT: Total Revenue` | 200, `Revenue=12252269.03` |
| Chart data API, top products | 200, 10 строк `product_name/Revenue` |
| Chart data API, revenue by month | 200, строки по месяцам |

Повторный запуск `superset-dashboards` показал `=` (reuse) для всех датасетов,
чартов и дашбордов; количество осталось 2 дашборда / 16 чартов.

---

## Сервисы и доступы

Актуально на финальное состояние (все долгоживущие сервисы подняты).

| Сервис (compose) | URL | Логин | Пароль | Назначение | Статус |
|---|---|---|---|---|---|
| `airflow-webserver` | http://localhost:8080 | admin | admin | Airflow UI / оркестрация | up, healthy |
| `airflow-scheduler` | — | — | — | Планировщик DAG | up, no healthcheck |
| `airflow-worker` | — | — | — | Celery worker | up, healthy |
| `airflow-triggerer` | — | — | — | Triggerer | up, no healthcheck |
| `airflow-init` | — | — | — | Миграции/создание admin (one-shot) | Exited (0) — успешно |
| `postgres-airflow` | — (внутренний 5432) | airflow | airflow | Метаданные Airflow | up, healthy |
| `redis` | — (внутренний 6379) | — | — | Celery broker + Superset results backend | up, healthy |
| `superset` | http://localhost:8088 | admin | admin | BI / дашборды | up, healthy |
| `superset-worker` | — | — | — | Celery worker Superset | up, healthy |
| `superset-init` | — | — | — | Миграции/StarRocks connection (one-shot) | Exited (0) — успешно |
| `superset-dashboards` | — | — | — | Создание дашбордов (one-shot) | Exited (0) — успешно |
| `minio` | http://localhost:9001 (Console), http://localhost:9000 (S3) | minioadmin | minioadmin | S3-хранилище | up, healthy |
| `starrocks` | http://localhost:8030 (FE), mysql://localhost:9030 | root | (пусто) | OLAP DWH | up, no healthcheck |
| `iceberg-rest` | http://localhost:8181 | — | — | Iceberg REST catalog | up, healthy |
| `spark-iceberg` | http://localhost:4040 (UI во время job); 8082/8888/10000 mapped | — | — | Spark ETL-контейнер | up, no healthcheck |
| `data-init` | — | — | — | Генерация supply_chain + retail в S3/StarRocks (one-shot) | Exited (0) — успешно |
| `dbt` | — | — | — | dbt run/test (one-shot) | Exited (0) — успешно |

Примечания:

- `spark-iceberg` не запускает Spark Master/Thrift/Jupyter как сервисы;
  порты 8082/8888/10000 проброшены, но фактически слушаются только во время
  соответствующих процессов. Spark UI 4040 доступен во время job.
- One-shot сервисы завершились с кодом 0 — это штатное завершение, а не
  остановка/падение. Долгоживущие сервисы оставлены поднятыми.

---

## Изменённые файлы

| Файл | Что изменено |
|---|---|
| `.env` | Удалены дубли Airflow-ключей; добавлены `AIRFLOW_ADMIN_USERNAME/PASSWORD`. |
| `docker-compose.yml` | `AIRFLOW__WEBSERVER__SECRET_KEY` во все Airflow-сервисы; `SUPERSET_CONFIG_PATH`/volume для results backend; зависимости Superset от Redis; новый сервис `superset-dashboards`; admin credentials из `.env`. |
| `airflow/dags/dbt_supply_chain_dag.py` | Добавлены `generate_retail`, `load_retail_to_starrocks`, env `RETAIL_*`, обновлены description/tags. |
| `dbt/scripts/generate_retail.py` | Новый генератор retail (11 таблиц, seed=42). |
| `dbt/scripts/load_retail_to_starrocks.py` | Новый загрузчик retail в `analytics.raw_retail_*`. |
| `dbt/scripts/init.sh` | Добавлены шаги retail generation/loading. |
| `project/models/staging/retail/sources.yml` | Новый source `retail_raw` (11 таблиц). |
| `project/models/staging/retail/stg_retail__*.sql` | 11 новых staging-моделей. |
| `project/models/marts/retail/mart_retail__*.sql` | 5 новых mart-моделей. |
| `project/models/marts/retail/schema.yml` | 10 новых тестов. |
| `superset/init/create_all_dashboards.py` | Новый идемпотентный скрипт двух дашбордов. |
| `superset/superset_config.py` | `RESULTS_BACKEND` на Redis (db 4), SECRET_KEY из env. |
| `start-superset.ps1` | Запуск Redis и `superset-dashboards`. |
| `start-all.ps1` | Запуск Redis на раннем шаге и `superset-dashboards`. |
| `REPORT_ITERATION_2.md` | Этот отчёт. |

Артефакты запуска (`project/target`, `project/logs`, `airflow/logs`) обновлены
проверочными запусками; вручную не редактировались.

---

## Известные ограничения

1. **Iceberg REST fixture** хранит метаданные в `/tmp/iceberg_catalog.db`
   внутри контейнера. После пересоздания контейнера нужно повторно выполнить
   `spark_etl_supply_chain.py`. В этой итерации так и сделано; таблица
   `lakehouse.supply_chain.suppliers` восстановлена (5000 строк).
2. **`spark_etl_dag`** по-прежнему отсутствует. Он не добавлялся: Airflow-контейнер
   не имеет доступа к Docker socket и Spark runtime, поэтому DAG был бы
   нерабочим. Spark ETL запускается вручную/через `spark-submit`.
3. **One-shot сервисы** (`airflow-init`, `data-init`, `dbt`, `superset-init`,
   `superset-dashboards`) не могут «висеть» запущенными; они завершаются с кодом 0.
4. **Spark UI** на 4040 доступен только во время выполнения Spark job.
   Порты 8082/8888/10000 проброшены, но master/Jupyter/Thrift не запущены.
5. **Superset results backend** использует общий Redis (db 4). Скрипты
   `start-superset.ps1` и `start-all.ps1` теперь поднимают Redis заранее.
6. В Airflow-образе остаётся pip-предупреждение о неиспользуемых providers
   (`common-sql 1.10.1` vs требование части providers). На ядро Airflow,
   `BashOperator`, DAG и вход admin не влияет; `dags list-import-errors` пуст.
7. **MOEX-модели** (из предыдущей итерации) сохранены; они не входят в
   retail/supply-chain бизнес-направления и не мешают пайплайну.

---

## Итоговый статус

**READY.**

Критерии итерации выполнены:

- Airflow `admin/admin` работает; `POST /login/` возвращает 302 → `/home`,
  `/home` — 200; CSRF не отключался.
- Retail: 11 таблиц сгенерированы, загружены в MinIO и StarRocks;
  11 stg + 5 mart моделей материализуются; `dbt test` PASS=19.
- Superset: 2 дашборда (`Supply Chain Overview`, `Retail Overview`) по 8 чартов;
  страницы открываются, чарты отдают непустые данные.
- Supply chain не сломан; Spark/Iceberg и StarRocks external catalog работают.
- Отчёт содержит раздел «Сервисы и доступы».
- Все долгоживущие сервисы оставлены поднятыми; `docker compose down` не выполнялся.
