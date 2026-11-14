# Data Platform — Lakehouse на Trino + Iceberg

Локальный lakehouse на Docker Compose:

```
synthetic data -> MinIO/S3 -> Spark -> Iceberg -> Trino -> dbt-trino -> Superset
```

StarRocks удалён. Trino — единственный SQL-слой, все таблицы живут в
Iceberg на S3.

> **Документация:** [`docs/README.md`](docs/README.md)
> **Запуск:** [`docs/RUNBOOK.md`](docs/RUNBOOK.md)
> **Сборка:** [`docs/BUILD.md`](docs/BUILD.md)
> **Миграция:** [`trino_migration.md`](trino_migration.md)

---

## Стек

| Компонент | Версия | Роль |
|---|---|---|
| Trino | 484 | SQL-движок |
| Iceberg | 1.4.3 / REST fixture 1.10.1 | табличный формат |
| Spark | 3.5.6 | CSV → Iceberg |
| MinIO | latest | S3 |
| dbt-core | 1.6.2 | трансформации |
| dbt-trino | 1.6.2 | адаптер |
| Superset | 4.1.2 | BI |
| Airflow | 2.10.5 | оркестрация |

---

## Быстрый старт

```powershell
docker compose up -d --build
docker compose ps -a
```

> Первый запуск — **20–30 минут** (100k supply + 200k retail + Spark ETL).

Ожидаемо:

- long-running сервисы `Up`;
- one-shot `data-init`, `spark-etl`, `dbt`, `superset-init`,
  `superset-dashboards`, `airflow-init` — `Exited (0)`;
- `dbt` — `PASS=37`, тесты `PASS=19`.

---

## Доступы

| Сервис | URL / порт | Логин / пароль |
|---|---|---|
| Trino | localhost:8081 (`iceberg.analytics`) | trino / (пусто) |
| Airflow | http://localhost:8080 | admin / admin |
| Superset | http://localhost:8088 | admin / admin |
| MinIO | http://localhost:9001 | minioadmin / minioadmin |
| Trino UI | http://localhost:8081 | — |

DBeaver:

```text
Driver:   Trino
JDBC:     jdbc:trino://localhost:8081/iceberg/analytics
User:     trino
Password: (пусто)
```

---

## Структура

```
dbt_sample/
├── airflow/            # DAG + Airflow image
├── dbt/                # dbt-trino образ, профиль, скрипты
├── project/            # dbt-проект: staging + marts
├── spark/              # Spark config + jobs (CSV → Iceberg)
├── trino/              # Trino config + Iceberg catalog
├── superset/           # Superset image + init/dashboards
├── scripts/            # windows/linux запуск
├── docs/               # документация
└── trino_migration.md  # отчёт миграции
```

---

## Поток данных

1. `data-init` — генерирует CSV в MinIO;
2. `spark-etl` — пишет Iceberg `lakehouse.analytics.raw_*`;
3. `dbt` — строит 26 staging views и 11 marts;
4. Trino читает `iceberg.analytics`;
5. Superset/DBeaver ходят в Trino.

---

## Факты

- 26 raw-таблиц в Iceberg;
- 37 dbt-моделей, 19 тестов;
- `raw_suppliers` = 100 000;
- `raw_retail_orders` = 200 000;
- `raw_retail_order_items` = 379 702;
- 2 дашборда Superset, 16 чартов.

---

## Полезные команды

```powershell
# Trino
docker exec trino trino --execute "SHOW TABLES FROM iceberg.analytics"

# dbt
docker compose run --rm --no-deps --entrypoint dbt dbt run `
  --profiles-dir /dbt/profiles --project-dir /dbt/project

# Spark ETL
docker compose run --rm --no-deps spark-etl

# Airflow DAG
docker exec airflow_scheduler airflow dags list
```

---

## Чего больше нет

StarRocks, `dbt-starrocks`, `FILES()`, портов 8030/9030/8040,
`starrocks_data` и StarRocks external catalog.
