# Модуль 04 — генерация данных

**Файлы модуля:**

- `dbt/scripts/generate_and_upload.py` — supply chain
- `dbt/scripts/generate_retail.py` — retail / e-commerce
- `dbt/scripts/load_s3_to_starrocks.py` — supply chain loader
- `dbt/scripts/load_retail_to_starrocks.py` — retail loader
- `dbt/scripts/load_moex_to_s3.py`, `load_moex_to_starrocks.sql`,
  `create_moex_table.sql` — опциональная MOEX-ветка

---

## 1. Роль модуля

Модуль создаёт синтетические данные, которых в проекте нет «из коробки».
Данные детерминированные: одинаковый seed даёт одинаковый набор.

Два независимых направления:

| Направление | Генератор | S3 prefix | StarRocks |
|---|---|---|---|
| Supply chain | `generate_and_upload.py` | `stg/{table}/{date}/` | `raw_{table}` |
| Retail | `generate_retail.py` | `retail/stg/{table}/{date}/` | `raw_retail_{table}` |

Префиксы не пересекаются, поэтому направления не ломают друг друга.

---

## 2. Supply chain: `generate_and_upload.py`

### 2.1. Что генерирует

15 таблиц, ~5000 строк на основную таблицу, до 120 колонок:

```
suppliers
supply_contracts
supply_orders
supply_items
shipments
warehouses
deliveries
invoices
payments
quality_checks
returns
inventory_movements
transport_routes
customs_declarations
supplier_ratings
```

Каждая таблица описана в списке `TABLES`:

```python
TABLES = [
    ("suppliers", [core columns...], []),
    ("supply_contracts", [...], [("supplier_id", "suppliers")]),
    ...
]
```

- первый элемент — имя таблицы;
- второй — обязательные/core-колонки;
- третий — foreign keys: `(имя_колонки, таблица_источник)`.

Дополнительные колонки берутся из `COLUMN_POOL` (около 120 типов:
коды, даты, деньги, количества, веса, адреса, статусы, bool, координаты,
текст, email, URL).

### 2.2. Seed и воспроизводимость

```python
RANDOM_SEED = int(os.getenv("RANDOM_SEED", "42"))
rng = random.Random(f"{RANDOM_SEED}-{table_name}")
```

Одинаковый `RANDOM_SEED` → одинаковые данные. Для другой генерации:

```powershell
$env:RANDOM_SEED="43"
```

### 2.3. Переменные окружения

| Переменная | Default | Значение |
|---|---|---|
| `RANDOM_SEED` | `42` | seed |
| `ROWS` | `5000` | строк на таблицу |
| `CHUNK_SIZE` | `2500` | строк в CSV-файле |
| `COLUMNS_PER_TABLE` | `120` | колонок |
| `LAYER` | `stg` | S3-префикс |
| `PARTITION_DATE` | текущая UTC-дата | папка даты |
| `CLEAN_BEFORE_UPLOAD` | `true` | удалять старый prefix |
| `WRITE_LOCAL` | `false` | писать ли CSV на диск |
| `SCHEMA_JSON_PATH` | `/dbt/_schema.json` | схема для загрузчика |
| `MINIO_*` | см. `.env` | S3 |
| `STARROCKS_*` | см. `.env` | не используется генератором, но нужно loader'у |

### 2.4. Что происходит при запуске

1. Подключается к MinIO (boto3, path-style).
2. Создаёт bucket `dbt-bucket`, если его нет.
3. Для каждой таблицы:
   - генерирует строки;
   - при `CLEAN_BEFORE_UPLOAD=true` удаляет старые объекты
     `stg/{table}/`;
   - пишет CSV частями по `CHUNK_SIZE`:
     `s3://dbt-bucket/stg/{table}/{date}/{table}_part_001.csv`;
4. Сохраняет схему в `/tmp/_schema.json` или `/dbt/_schema.json`.
5. **Перегенерирует dbt-модели**:
   - `project/models/staging/stg_{table}.sql`;
   - `project/models/staging/sources.yml`.

### 2.5. Важное следствие

15 файлов `project/models/staging/stg_*.sql` — **генерируемые**. Не
редактируйте их вручную: следующий `data-init` перезапишет изменения.
Свои модели кладите в отдельные файлы.

---

## 3. Retail: `generate_retail.py`

### 3.1. Что генерирует

11 связанных таблиц:

| Таблица | Строк | Смысл |
|---|---:|---|
| `categories` | 20 | Категории товаров |
| `products` | 500 | Товары |
| `customers` | 3000 | Клиенты |
| `stores` | 50 | Магазины |
| `promotions` | 31 | Промо (0 = без промо) |
| `orders` | 5000 | Заказы |
| `order_items` | ~9500 | Позиции заказов |
| `payments` | 5000 | Платежи |
| `shipments` | ~4100 | Отгрузки |
| `returns` | ~290 | Возвраты |
| `reviews` | 2000 | Отзывы |

### 3.2. Seed и объёмы

```python
SEED      = int(os.getenv("RETAIL_SEED", "42"))
CUSTOMERS = int(os.getenv("RETAIL_CUSTOMERS", "3000"))
ORDERS    = int(os.getenv("RETAIL_ORDERS", "5000"))
PRODUCTS  = int(os.getenv("RETAIL_PRODUCTS", "500"))
STORES    = int(os.getenv("RETAIL_STORES", "50"))
PROMOTIONS= int(os.getenv("RETAIL_PROMOTIONS", "30"))
REVIEWS   = int(os.getenv("RETAIL_REVIEWS", "2000"))
```

Все генерации используют `random.Random(SEED)`.

### 3.3. Связи

- `products.category_id → categories`
- `orders.customer_id → customers`
- `orders.store_id → stores`
- `orders.promotion_id → promotions` (0 = без промо)
- `order_items.order_id → orders`
- `order_items.product_id → products`
- `payments.order_id → orders`
- `shipments.order_id → orders`
- `returns.order_id → orders`
- `reviews.product_id/customer_id/order_id` → соответствующие таблицы

Суммы заказов считаются из `order_items`:

```
subtotal      = сумма unit_price * quantity
discount      = скидка промо
tax           = 8% от net
total_amount  = net + shipping + tax
```

### 3.4. S3-путь

```
s3://dbt-bucket/retail/stg/{table}/{date}/{table}_part_001.csv
```

Отдельный префикс `retail/stg` гарантирует, что supply chain и retail не
пересекутся.

### 3.5. Схема

`/tmp/_retail_schema.json`:

```json
{
  "orders": {
    "columns": [
      ["order_id", "INT"],
      ["customer_id", "INT"],
      ...
    ]
  }
}
```

Загрузчик `load_retail_to_starrocks.py` читает этот файл и создаёт
`analytics.raw_retail_*`.

---

## 4. Загрузчики в StarRocks

### 4.1. Supply chain

`dbt/scripts/load_s3_to_starrocks.py`:

1. ждёт StarRocks (`SHOW BACKENDS`, до 240 секунд);
2. создаёт `analytics`;
3. для каждой таблицы:
   - `DROP TABLE IF EXISTS raw_{table}`;
   - `CREATE TABLE ... DUPLICATE KEY ... DISTRIBUTED BY HASH ...`;
4. создаёт `raw_moex_prices` (если нет) для MOEX-модели;
5. грузит CSV по одному файлу через `FILES()`;
6. считает `COUNT(*)`.

Почему по одному файлу: StarRocks `FILES()` с wildcard иногда даёт
`schema is null`; пофайловая загрузка стабильнее.

### 4.2. Retail

`dbt/scripts/load_retail_to_starrocks.py`:

1. читает `/tmp/_retail_schema.json`;
2. ждёт StarRocks;
3. создаёт `raw_retail_{table}`;
4. грузит файлы из `retail/stg/{table}/`;
5. считает строки.

---

## 5. Как запускать вручную

### 5.1. Через `data-init`

```powershell
docker compose up -d --force-recreate data-init
docker compose logs -f data-init
```

`data-init` выполнит оба направления.

### 5.2. Только retail-генератор

Внутри контейнера `dbt_data_init` или `dbt_runner`:

```powershell
docker compose run --rm --entrypoint python dbt /dbt/scripts/generate_retail.py
```

Но загрузчик должен быть запущен в том же контейнере, где лежит
`/tmp/_retail_schema.json`. Проще запускать через `data-init` или DAG.

### 5.3. Через Airflow

Задачи `generate_retail` и `load_retail_to_starrocks` в DAG.

---

## 6. MOEX (опционально)

Файлы:

- `dbt/scripts/load_moex_to_s3.py`;
- `dbt/scripts/create_moex_table.sql`;
- `dbt/scripts/load_moex_to_starrocks.sql`;
- `project/models/staging/stg_moex_prices.sql`;
- `project/models/marts/mart_moex_daily_returns.sql`;
- `.env`: `MOEX_TICKERS`, `MOEX_FROM`, `MOEX_TO`, `MOEX_BOARD`.

MOEX не входит в основной DAG. `load_s3_to_starrocks.py` создаёт пустую
`raw_moex_prices`, чтобы dbt-модель не падала на чистом окружении. Если
нужны реальные данные — запускайте MOEX-скрипты вручную.

---

## 7. Правила изменения данных

1. **Не меняйте seed без причины** — сломается воспроизводимость.
2. **Новые таблицы добавляйте аддитивно** — не удаляйте старые.
3. **Соблюдайте FK** — генератор должен ссылаться на существующие ID.
4. **Держите объём разумным** — 1000–5000 строк на основную таблицу.
5. **Проверяйте загрузку** — `COUNT(*)` в StarRocks.
6. **Не редактируйте генерируемые `stg_*.sql`** — правьте генератор.

Подробный рецепт добавления таблицы — в
[`../DEVELOPMENT_GUIDE.md`](../DEVELOPMENT_GUIDE.md).

---

## 8. Частые ошибки

| Ошибка | Причина | Решение |
|---|---|---|
| `NoSuchBucket` | bucket не создан | генератор создаёт сам; проверить MinIO |
| `AccessDenied` | неверные ключи | `.env` / DAG ENV |
| `ModuleNotFoundError: boto3` | запуск на хосте | запускать внутри контейнера |
| `schema is null` при `FILES()` | wildcard/credentials | грузить по одному файлу, path-style |
| `Table raw_* not found` | loader не запускался | `data-init` |
| `raw_retail_* not found` | retail loader не запускался | `data-init`/DAG |
| `PermissionError: /dbt/_schema.json` | нет прав | `/tmp/_retail_schema.json` |
| dbt-модель пропала | generator перезаписал staging | не хранить ручные правки в генерируемых файлах |

---

## 9. Связанные документы

- [`03-dbt.md`](03-dbt.md)
- [`05-starrocks.md`](05-starrocks.md)
- [`07-minio.md`](07-minio.md)
- [`../DEVELOPMENT_GUIDE.md`](../DEVELOPMENT_GUIDE.md)
