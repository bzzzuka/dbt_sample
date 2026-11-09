# Архитектура проекта

**Актуально на:** 2026-11-09

Этот файл объясняет, как сервисы и данные связаны между собой. Читайте его
после [`README.md`](README.md), но до погружения в модули.

---

## 1. Общая картина

Проект состоит из двух параллельных путей обработки данных.

### Путь A — классический DWH (основной)

```
CSV в MinIO
    |
    v
StarRocks raw_*
    |
    v
dbt staging (view)
    |
    v
dbt marts (table)
    |
    v
Superset dashboards
```

### Путь B — lakehouse

```
CSV в MinIO
    |
    v
Spark ETL
    |
    v
Iceberg table в MinIO (Parquet + metadata)
    |
    v
Iceberg REST catalog
    |
    v
StarRocks external catalog iceberg_lakehouse
    |
    v
Superset / SQL-клиенты
```

Путь A используется для витрин `mart_supply_chain_*` и `mart_retail_*`.
Путь B демонстрирует open table format и чтение Iceberg без копирования
данных в StarRocks.

### Кто кого запускает

```
Airflow scheduler
    |
    |-- generate_and_upload.py  -> MinIO + StarRocks raw_*
    |-- load_s3_to_starrocks.py
    |-- generate_retail.py      -> MinIO retail/stg
    |-- load_retail_to_starrocks.py -> StarRocks raw_retail_*
    |-- dbt run                 -> stg_* views + mart_* tables
    |-- dbt test                -> 19 тестов
```

Spark ETL пока запускается **вручную** через `docker exec spark_iceberg
spark-submit ...`, а не из Airflow. Это осознанное ограничение: у Airflow
нет доступа к Docker socket и Spark runtime.

---

## 2. Сервисы

| Сервис | Образ | Роль | Порты | Зависит от | Healthcheck |
|---|---|---|---|---|---|
| `starrocks` | `starrocks/allin1-ubuntu:3.4-latest` | OLAP DWH, FE+BE | 8030, 9030, 8040 | — | нет |
| `minio` | `ghcr.io/coollabsio/minio:latest` | S3 | 9000, 9001 | — | `mc ready local` |
| `data-init` | `./dbt/Dockerfile` | one-shot: генерация и загрузка | — | starrocks, minio | нет |
| `dbt` | `./dbt/Dockerfile` | one-shot: `dbt debug/run/test` | — | data-init | нет |
| `superset` | `./superset/Dockerfile` | BI webserver | 8088 | superset-init, starrocks, redis | да |
| `superset-init` | `./superset/Dockerfile` | one-shot: миграции, admin, StarRocks connection | — | starrocks | нет |
| `superset-worker` | `./superset/Dockerfile` | Celery worker Superset | — | superset, redis | Celery ping |
| `superset-dashboards` | `./superset/Dockerfile` | one-shot: создание дашбордов | — | superset, redis | нет |
| `postgres-airflow` | `postgres:15-alpine` | метаданные Airflow | — | — | `pg_isready` |
| `redis` | `redis:7-alpine` | Celery broker + Superset results | внутренний 6379 | — | `redis-cli ping` |
| `airflow-init` | `./airflow/Dockerfile` | one-shot: миграции + admin | — | postgres, redis | нет |
| `airflow-webserver` | `dbt_sample-airflow:latest` | Airflow UI | 8080 | airflow-init | `/health` |
| `airflow-scheduler` | `dbt_sample-airflow:latest` | Планировщик | — | airflow-init | нет |
| `airflow-worker` | `dbt_sample-airflow:latest` | Celery worker | — | airflow-init | Celery ping |
| `airflow-triggerer` | `dbt_sample-airflow:latest` | Deferred operators | — | airflow-init | нет |
| `iceberg-rest` | `apache/iceberg-rest-fixture:1.10.1` | Iceberg REST catalog | 8181 | — | да |
| `spark-iceberg` | `apache/spark:3.5.6` | Spark ETL-контейнер | 4040, 8082, 8888, 10000 | iceberg-rest, minio | нет |

> `airflow-webserver`, `airflow-scheduler`, `airflow-worker`,
> `airflow-triggerer` используют один и тот же образ
> `dbt_sample-airflow:latest`, который собирается в сервисе `airflow-init`.

---

## 3. Сети и volumes

### Сеть

Все сервисы подключены к bridge-сети `dbt_network`. Внутри неё работают
DNS-имена сервисов:

- `starrocks:9030`
- `minio:9000`
- `iceberg-rest:8181`
- `postgres-airflow:5432`
- `redis:6379`

Поэтому в конфигурациях используется `host=starrocks`, а не `localhost`.
`localhost` внутри контейнера — это сам контейнер.

### Volumes

| Volume | Кто использует | Что хранит |
|---|---|---|
| `starrocks_data` | `starrocks` | Данные и метаданные StarRocks |
| `minio_data` | `minio` | CSV и Iceberg warehouse |
| `superset_home` | Superset-сервисы | SQLite-метаданные Superset |
| `postgres_airflow_data` | `postgres-airflow` | Метаданные Airflow |

Удаление volumes (`docker compose down -v`) стирает все данные и историю
запусков. Это полезно для чистого старта, но опасно для учебных результатов.

---

## 4. Слои данных и соглашения об именах

| Слой | Где | Материализация | Имя | Назначение |
|---|---|---|---|---|
| Raw supply chain | StarRocks | table | `raw_<table>` | Зеркало CSV из MinIO |
| Raw retail | StarRocks | table | `raw_retail_<table>` | Зеркало retail CSV |
| Staging supply chain | StarRocks | view | `stg_<table>` | Лёгкий слой над raw |
| Staging retail | StarRocks | view | `stg_retail__<table>` | Лёгкий слой над retail raw |
| Marts supply chain | StarRocks | table | `mart_<name>` | Аналитические витрины |
| Marts retail | StarRocks | table | `mart_retail__<name>` | Аналитические витрины |
| Lakehouse | MinIO | Iceberg | `lakehouse.supply_chain.<table>` | Open table format |
| Iceberg в StarRocks | StarRocks | external | `iceberg_lakehouse.supply_chain.<table>` | Чтение Iceberg |

### Почему двойное подчёркивание в retail

`stg_retail__orders` и `mart_retail__sales_by_month` используют `__`, чтобы
явно отделить домен (`retail`) от имени сущности. Это не требование dbt, а
договорённость проекта: так проще делать `--select "stg_retail__*"` и
визуально отличать retail от supply chain.

---

## 5. Поток данных по шагам

### 5.1. `data-init`

Файл: `dbt/scripts/init.sh`.

```
[1/4] generate_and_upload.py
      -> 15 CSV supply chain в s3://dbt-bucket/stg/{table}/{date}/
      -> /tmp/_schema.json
      -> перегенерация project/models/staging/stg_*.sql и sources.yml

[2/4] load_s3_to_starrocks.py
      -> analytics.raw_* (15 таблиц)
      -> analytics.raw_moex_prices (пустая/совместимая таблица)

[3/4] generate_retail.py
      -> 11 CSV retail в s3://dbt-bucket/retail/stg/{table}/{date}/
      -> /tmp/_retail_schema.json

[4/4] load_retail_to_starrocks.py
      -> analytics.raw_retail_* (11 таблиц)
```

### 5.2. `dbt`

Файл: `dbt/scripts/run_dbt.sh` (сервис `dbt`) или задачи `dbt_run` / `dbt_test`
в Airflow.

```
dbt debug -> проверка подключения к StarRocks
dbt run   -> stg_* (view) + mart_* (table)
dbt test  -> unique/not_null тесты
```

Фактически: 39 моделей, 19 тестов.

### 5.3. Spark + Iceberg

```
spark/jobs/etl_supply_chain.py
    -> читает s3a://dbt-bucket/stg/suppliers/*/*.csv
    -> пишет lakehouse.supply_chain.suppliers
    -> createOrReplace (полная перезапись)
```

Проверка:

```
spark/jobs/verify_iceberg.py
    -> SHOW CATALOGS
    -> SHOW NAMESPACES IN lakehouse
    -> SHOW TABLES IN lakehouse.supply_chain
    -> SELECT * ... LIMIT 5
```

### 5.4. StarRocks external catalog

Файл: `spark/init-starrocks.sql`.

```
CREATE EXTERNAL CATALOG iceberg_lakehouse
PROPERTIES (type=iceberg, catalog.type=rest, uri=http://iceberg-rest:8181, ...)
```

После этого:

```sql
SHOW CATALOGS;
SHOW DATABASES FROM iceberg_lakehouse;
SELECT COUNT(*) FROM iceberg_lakehouse.supply_chain.suppliers;
```

### 5.5. Superset

```
superset-init
    -> миграции метаданных
    -> admin/admin
    -> connection "StarRocks Analytics"

superset-dashboards
    -> 11 datasets
    -> 16 charts
    -> 2 dashboards
```

Дашборды строятся поверх `analytics.mart_*`, не поверх raw/staging.

---

## 6. Откуда берутся настройки

| Что | Файл | Как попадает в контейнер |
|---|---|---|
| Порты, volumes, зависимости | `docker-compose.yml` | Compose |
| Пользователи/пароли StarRocks, MinIO, Airflow | `.env` | Через `${...}` в `docker-compose.yml` |
| dbt-подключение | `dbt/profiles/profiles.yml` | Монтируется в Airflow, копируется в dbt-образ |
| Пути S3/Prefix | env-переменные в `docker-compose.yml` и DAG | `environment` / `ENV` |
| Spark/Iceberg | `spark/conf/spark-defaults.conf` | Volume в `spark-iceberg` |
| Superset | `superset/superset_config.py` | Volume в Superset-сервисы |
| StarRocks external catalog | `spark/init-starrocks.sql` | Применяется вручную |

> `.env` сам по себе **не** пробрасывает переменные в контейнер. Compose
> подставляет `${VAR}` в `docker-compose.yml`, а в контейнер переменная
> попадает только если она указана в `environment` сервиса. Это частая
> причина «почему мой `.env` не работает».

---

## 7. One-shot и long-running сервисы

### Long-running (должны быть `Up`)

`starrocks`, `minio`, `superset`, `superset-worker`, `postgres-airflow`,
`redis`, `airflow-webserver`, `airflow-scheduler`, `airflow-worker`,
`airflow-triggerer`, `iceberg-rest`, `spark-iceberg`.

### One-shot (должны завершиться `Exited (0)`)

`data-init`, `dbt`, `superset-init`, `superset-dashboards`, `airflow-init`.

`Exited (0)` — успех. `Exited (1+)` — ошибка, смотрите логи.

---

## 8. Принципы проекта

1. **Compute-storage separation** — данные в MinIO, вычислители независимы.
2. **Идемпотентность** — повторный запуск не должен плодить дубликаты.
   Генераторы чистят свои префиксы, dbt пересоздаёт модели, Superset
   использует `find_or_create`.
3. **Слои** — raw → staging → marts; не смешивайте слои.
4. **Конфигурация отдельно от кода** — `.env`, profiles, config-файлы.
5. **Один образ на группу сервисов** — Airflow-сервисы используют один образ.
6. **Явные зависимости** — `depends_on`, healthcheck, ожидание StarRocks.

---

## 9. Известные архитектурные ограничения

- StarRocks allin1 без healthcheck — используется `condition: service_started`.
- Iceberg REST fixture хранит метаданные в `/tmp` внутри контейнера:
  после пересоздания `iceberg-rest` каталог пуст, нужен повторный Spark ETL.
- Spark ETL обрабатывает только `suppliers`; остальные таблицы пока не
  переносятся в Iceberg.
- `spark_etl_dag` отсутствует: Spark запускается вручную.
- Airflow DAG содержит захардкоженные StarRocks/MinIO credentials в `ENV`;
  при изменении `.env` их нужно синхронизировать.
- dbt-starrocks 1.6.2 — самая стабильная версия для этого проекта; не
  обновляйте до 1.7+ без проверки.
- Superset results backend использует Redis (db 4); без Redis SQL Lab и
  часть чартов не работают.

---

## 10. Куда читать дальше

- Запуск и проверки — [`RUNBOOK.md`](RUNBOOK.md).
- Развитие — [`DEVELOPMENT_GUIDE.md`](DEVELOPMENT_GUIDE.md).
- Модули — [`modules/`](modules/).
