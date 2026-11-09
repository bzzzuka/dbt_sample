# Документация проекта dbt_sample

**Актуально на:** 2026-11-09  
**Для кого:** новый инженер, аналитик или DevOps, который впервые открыл проект.

Этот файл — главная точка входа. Он объясняет, из чего состоит проект,
где читать подробности и как быстро поднять стек. Подробная инструкция по
запуску — в [`RUNBOOK.md`](RUNBOOK.md), развитие проекта — в
[`DEVELOPMENT_GUIDE.md`](DEVELOPMENT_GUIDE.md).

> **Важно:** корневой `README.md` и README внутри модулей описывают более
> раннюю версию проекта (15 staging + 6 marts, без retail). Актуальное
> состояние — в `docs/`. Если числа расходятся, верьте `docs/` и фактическим
> файлам проекта.

---

## Что это за проект

Локальный **lakehouse** для обучения data engineering. Всё запускается через
Docker Compose на одной машине:

- генерирует синтетические данные о поставках и retail/e-commerce;
- складывает CSV в S3-совместимый MinIO;
- грузит данные в StarRocks;
- трансформирует dbt (raw → staging → marts);
- строит Iceberg-таблицы через Spark;
- читает Iceberg из StarRocks через external catalog;
- показывает аналитику в Superset;
- оркестрирует пайплайн через Airflow.

### Стек

| Компонент | Версия | Роль |
|---|---|---|
| Airflow | 2.10.5 (Python 3.11) | Оркестрация |
| dbt | 1.6.2 + dbt-starrocks 1.6.2 | SQL-трансформации |
| StarRocks | 3.4 allin1 | OLAP DWH |
| MinIO | latest (coollabsio) | S3-хранилище |
| Spark | 3.5.6 | ETL в Iceberg |
| Iceberg | 1.4.3 (Spark), REST fixture 1.10.1 | Lakehouse |
| Superset | 4.1.2 | BI и дашборды |

---

## С чего начать: маршрут чтения

1. **Хочу просто запустить** → [`RUNBOOK.md`](RUNBOOK.md), раздел «Полный запуск».
2. **Хочу понять, как всё связано** → [`ARCHITECTURE.md`](ARCHITECTURE.md).
3. **Хочу разобраться в конкретном модуле** → файлы в [`modules/`](modules/).
4. **Хочу добавить новую таблицу, витрину, DAG или дашборд** →
   [`DEVELOPMENT_GUIDE.md`](DEVELOPMENT_GUIDE.md).
5. **Хочу выбрать новую цель/направление** → [`ROADMAP.md`](ROADMAP.md).
6. **Хочу проверить, что всё работает** →
   [`modules/10-checks-and-tests.md`](modules/10-checks-and-tests.md).

---

## Быстрый старт (5–10 минут)

### 1. Требования

- Docker Desktop (Windows/macOS) или Docker Engine (Linux).
- Docker Compose v2.
- **8 ГБ ОЗУ минимум**, лучше 16 ГБ.
- ~15 ГБ свободного диска.
- Windows PowerShell (скрипты проекта — PowerShell).

Проверить Docker:

```powershell
docker version
docker compose version
docker info | Select-String "Total Memory"
```

### 2. Проверить `.env`

Файл `.env` уже содержит локальные значения. Основные:

```env
STARROCKS_HOST=starrocks
STARROCKS_PORT=9030
STARROCKS_USER=root
STARROCKS_PASSWORD=
STARROCKS_SCHEMA=analytics
STARROCKS_CATALOG=default_catalog

MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin
MINIO_ENDPOINT=http://minio:9000
MINIO_BUCKET=dbt-bucket
MINIO_REGION=us-east-1

AIRFLOW_ADMIN_USERNAME=admin
AIRFLOW_ADMIN_PASSWORD=admin
AIRFLOW_FERNET_KEY=...
AIRFLOW__WEBSERVER__SECRET_KEY=airflow_webserver_secret_local
```

Не коммить реальные секреты. Для локального учебного проекта значения
`admin/admin` и `minioadmin/minioadmin` допустимы.

### 3. Запустить весь стек

Рекомендуемый путь:

```powershell
docker compose config
docker compose up -d --build
docker compose ps -a
```

Первый запуск может занять несколько минут: собираются образы Airflow,
dbt и Superset, а Spark при первом ETL скачивает Maven-зависимости.

### 4. Открыть интерфейсы

| Сервис | URL | Логин / пароль |
|---|---|---|
| Airflow | http://localhost:8080 | `admin` / `admin` |
| Superset | http://localhost:8088 | `admin` / `admin` |
| MinIO Console | http://localhost:9001 | `minioadmin` / `minioadmin` |
| MinIO S3 API | http://localhost:9000 | `minioadmin` / `minioadmin` |
| StarRocks FE | http://localhost:8030 | `root` / (пусто) |
| StarRocks SQL | `mysql://localhost:9030` | `root` / (пусто) |
| Iceberg REST | http://localhost:8181 | — |
| Spark UI | http://localhost:4040 | — (только во время job) |

### 5. Проверить данные и DAG

```powershell
# DAG виден?
docker exec airflow_scheduler airflow dags list

# Снять с паузы и запустить
docker exec airflow_scheduler airflow dags unpause dbt_supply_chain_pipeline
docker exec airflow_scheduler airflow dags trigger dbt_supply_chain_pipeline

# Статус запусков
docker exec airflow_scheduler airflow dags list-runs -d dbt_supply_chain_pipeline
```

> Новые DAG создаются на паузе (`DAGS_ARE_PAUSED_AT_CREATION=True`). После
> первого запуска стека DAG нужно снять с паузы вручную.

Проверить StarRocks:

```powershell
docker exec starrocks mysql -h 127.0.0.1 -P 9030 -uroot -e "USE analytics; SHOW TABLES;"
docker exec starrocks mysql -h 127.0.0.1 -P 9030 -uroot -e "SELECT COUNT(*) FROM analytics.mart_retail__sales_by_month;"
```

Проверить Superset:

- открыть http://localhost:8088;
- войти `admin/admin`;
- открыть `Supply Chain Overview` и `Retail Overview`.

---

## Фактическое состояние проекта

На текущий момент в dbt-проекте:

| Слой | Количество | Что входит |
|---|---:|---|
| Staging supply chain | 15 | `stg_suppliers`, `stg_supply_orders`, ... |
| Staging MOEX (опционально) | 1 | `stg_moex_prices` |
| Staging retail | 11 | `stg_retail__customers`, `stg_retail__orders`, ... |
| Marts supply chain | 6 | `mart_supplier_performance`, `mart_delivery_kpi`, ... |
| Marts MOEX (опционально) | 1 | `mart_moex_daily_returns` |
| Marts retail | 5 | `mart_retail__sales_by_month`, `mart_retail__customer_ltv`, ... |
| **Всего моделей** | **39** | `dbt run` → PASS=39 |
| **Тестов** | **19** | `dbt test` → PASS=19 |
| **Дашбордов Superset** | 2 | `Supply Chain Overview`, `Retail Overview` |
| **Чартов Superset** | 16 | по 8 на дашборд |

---

## Карта документации

### Главные файлы

| Файл | Что внутри |
|---|---|
| [`RUNBOOK.md`](RUNBOOK.md) | Как запускать, останавливать, проверять и чинить стек |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Архитектура, потоки данных, сервисы, порты, volumes |
| [`DATA_MODEL.md`](DATA_MODEL.md) | Таблицы, связи, витрины, lineage |
| [`DEVELOPMENT_GUIDE.md`](DEVELOPMENT_GUIDE.md) | Как добавлять таблицы, модели, DAG, дашборды и новые направления |
| [`ROADMAP.md`](ROADMAP.md) | Идеи и приоритеты для новых целей проекта |

### Модули

| Файл | Модуль |
|---|---|
| [`modules/01-infrastructure.md`](modules/01-infrastructure.md) | Docker Compose, `.env`, сети, volumes, порты |
| [`modules/02-airflow.md`](modules/02-airflow.md) | Airflow, DAG, авторизация, worker/scheduler |
| [`modules/03-dbt.md`](modules/03-dbt.md) | dbt, профили, модели, тесты, скрипты |
| [`modules/04-data-generation.md`](modules/04-data-generation.md) | Генерация supply chain и retail данных |
| [`modules/05-starrocks.md`](modules/05-starrocks.md) | StarRocks, raw/stg/mart, external catalog |
| [`modules/06-spark-iceberg.md`](modules/06-spark-iceberg.md) | Spark, Iceberg, REST catalog, ETL |
| [`modules/07-minio.md`](modules/07-minio.md) | MinIO, bucket, S3-пути, `mc` |
| [`modules/08-superset.md`](modules/08-superset.md) | Superset, init, дашборды, Redis results backend |
| [`modules/09-scripts-and-legacy.md`](modules/09-scripts-and-legacy.md) | Start-скрипты, legacy-генераторы, отчёты |
| [`modules/10-checks-and-tests.md`](modules/10-checks-and-tests.md) | Полный чек-лист проверки проекта |

---

## Три важных правила

1. **One-shot сервисы завершаются с кодом 0 — это нормально.**
   `airflow-init`, `data-init`, `dbt`, `superset-init`, `superset-dashboards`
   созданы для одноразовой работы. В `docker compose ps -a` они будут
   `Exited (0)`. Долгоживущие сервисы (Airflow, StarRocks, MinIO, Superset,
   Spark, Iceberg REST, Postgres, Redis) должны быть `Up`.

2. **Не запускайте legacy-генераторы `setup_starrocks.py` и `make_dag.py`.**
   Они перезапишут актуальные `docker-compose.yml`, DAG и модели старой
   версией без retail и Superset. Подробности —
   [`modules/09-scripts-and-legacy.md`](modules/09-scripts-and-legacy.md).

3. **Данные и метаданные живут в Docker volumes.**
   `docker compose down` сохраняет данные, `docker compose down -v` удаляет
   StarRocks, MinIO, Superset и Postgres. Используйте `-v` только если
   действительно хотите полный сброс.

---

## Если что-то не работает

Быстрый маршрут:

```powershell
docker compose ps -a
docker compose logs --tail=100 <service>
```

Самые частые причины:

| Симптом | Куда смотреть |
|---|---|
| Airflow не пускает `admin/admin` | [`modules/02-airflow.md`](modules/02-airflow.md), раздел «Авторизация» |
| Порт 8080 занят | `Get-NetTCPConnection -LocalPort 8080`; остановить чужой контейнер |
| `dbt: command not found` в Airflow | Проверить `PATH` в DAG и образ Airflow |
| Superset не строит графики | Redis results backend и `superset_config.py` |
| StarRocks не видит Iceberg | Пересоздать external catalog и повторно запустить Spark ETL |
| `Exited (137)` | OOM: увеличить память Docker или запускать по режимам |

Полный troubleshooting — в [`RUNBOOK.md`](RUNBOOK.md).
