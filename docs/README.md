# Документация проекта dbt_sample (Trino + Iceberg)

**Актуально на:** 2026-11-13

**Стек:** synthetic data → MinIO/S3 → Spark → Iceberg → Trino → dbt-trino → Superset.

StarRocks из проекта удалён. Все raw/staging/marts живут в Iceberg,
Trino — единственный SQL-слой.

---

## 1. Что это за проект

Локальный lakehouse:

- генераторы создают synthetic supply-chain и retail данные;
- CSV уезжают в MinIO (S3);
- Spark читает CSV и пишет Iceberg-таблицы;
- Iceberg REST catalog хранит metadata;
- Trino читает Iceberg;
- dbt-trino строит staging views и marts-таблицы;
- Superset и DBeaver ходят в Trino;
- Airflow запускает генерацию, Spark ETL и dbt.

---

## 2. Быстрый старт

```powershell
docker compose up -d --build
docker compose ps -a
```

> Первый запуск — **20–30 минут**: генерация 100k supply + 200k retail
> и Spark ETL.

Порядок:

1. `minio` — S3;
2. `data-init` — генерация CSV в MinIO;
3. `spark-etl` — CSV → Iceberg;
4. `trino` — SQL-движок;
5. `dbt` — 37 моделей / 19 тестов;
6. `superset-init` / `superset` / `superset-dashboards`;
7. Airflow (webserver/scheduler/worker/triggerer).

One-shot сервисы (`data-init`, `spark-etl`, `dbt`, `superset-init`,
`superset-dashboards`, `airflow-init`) должны завершиться `Exited (0)`.

---

## 3. Доступы

| Сервис | URL / порт | Логин | Пароль |
|---|---|---|---|
| Trino / DBeaver | `localhost:8081`, catalog `iceberg`, schema `analytics` | `trino` | (пусто) |
| Trino UI | http://localhost:8081 | — | — |
| MinIO Console | http://localhost:9001 | minioadmin | minioadmin |
| MinIO S3 | http://localhost:9000 | minioadmin | minioadmin |
| Airflow | http://localhost:8080 | admin | admin |
| Superset | http://localhost:8088 | admin | admin |
| Iceberg REST | http://localhost:8181 | — | — |
| Spark UI | http://localhost:4040 | — | — |

DBeaver:

```text
Driver:   Trino
JDBC:     jdbc:trino://localhost:8081/iceberg/analytics
User:     trino
Password: (пусто)
```

---

## 4. Фактическое состояние

| Слой | Количество |
|---|---:|
| Iceberg raw supply-chain | 15 |
| Iceberg raw retail | 11 |
| dbt staging models | 26 |
| dbt marts | 11 |
| **Всего dbt-моделей** | **37** |
| **Тестов** | **19** |
| Superset dashboards | 2 |
| Superset charts | 16 |

Ключевые объёмы:

| Таблица | Строк |
|---|---:|
| `raw_suppliers` | 100 000 |
| `raw_supply_orders` | 100 000 |
| `raw_retail_orders` | 200 000 |
| `raw_retail_order_items` | 379 702 |
| `mart_supplier_performance` | 100 000 |
| `mart_warehouse_activity` | 100 000 |
| `mart_retail__customer_ltv` | 50 000 |

---

## 5. Карта документации

### Главные файлы

| Файл | Что внутри |
|---|---|
| [`BUILD.md`](BUILD.md) | Сборка на Windows/Linux/macOS |
| [`RUNBOOK.md`](RUNBOOK.md) | Запуск, проверки, troubleshooting |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Архитектура Trino + Iceberg |
| [`DATA_MODEL.md`](DATA_MODEL.md) | Таблицы, связи, витрины |
| [`DEVELOPMENT_GUIDE.md`](DEVELOPMENT_GUIDE.md) | Как развивать проект |
| [`ROADMAP.md`](ROADMAP.md) | Идеи и приоритеты |
| [`../trino_migration.md`](../trino_migration.md) | Полная миграция StarRocks → Trino |

### Модули

| Файл | Модуль |
|---|---|
| [`modules/01-infrastructure.md`](modules/01-infrastructure.md) | Docker Compose |
| [`modules/02-airflow.md`](modules/02-airflow.md) | Airflow |
| [`modules/03-dbt.md`](modules/03-dbt.md) | dbt-trino |
| [`modules/04-data-generation.md`](modules/04-data-generation.md) | Генерация данных |
| [`modules/05-trino.md`](modules/05-trino.md) | Trino + Iceberg |
| [`modules/06-spark-iceberg.md`](modules/06-spark-iceberg.md) | Spark + Iceberg |
| [`modules/07-minio.md`](modules/07-minio.md) | MinIO |
| [`modules/08-superset.md`](modules/08-superset.md) | Superset |
| [`modules/09-scripts-and-legacy.md`](modules/09-scripts-and-legacy.md) | Скрипты |
| [`modules/10-checks-and-tests.md`](modules/10-checks-and-tests.md) | Проверки |

---

## 6. Три важных правила

1. **Trino — не хранилище.** Все данные в Iceberg на S3.
2. **One-shot сервисы** завершаются `Exited (0)` — это успех.
3. **Iceberg REST fixture** учебный; для production нужен
   Postgres JDBC/Nessie, иначе metadata теряются при пересоздании.
