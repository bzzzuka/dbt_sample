# Data Platform — Lakehouse Project

Полный локальный стек для data engineering: генерация → S3 → lakehouse → аналитика.
Включает оркестрацию, трансформации, BI и работу с современным табличным форматом Iceberg.

## Содержание

- [О проекте](#о-проекте)
- [Архитектура](#архитектура)
- [Стек](#стек)
- [Структура проекта](#структура-проекта)
- [Быстрый старт](#быстрый-старт)
- [Как всё устроено](#как-всё-устроено)
- [Интерфейсы](#интерфейсы)
- [Полезные команды](#полезные-команды)
- [Troubleshooting](#troubleshooting)
- [Roadmap](#roadmap)

---

## О проекте

Учебный **local lakehouse** — полный цикл data engineering на одной машине через Docker Compose.

**Что умеет:**

- Генерирует синтетические данные (15 таблиц × ~120 колонок о поставках)
- Хранит их в S3-совместимом хранилище (MinIO)
- Трансформирует через dbt (staging + marts)
- Анализирует в StarRocks (OLAP-база)
- Строит lakehouse-слой: Spark + Iceberg
- Визуализирует в Superset
- Оркестрирует через Airflow

**Ключевые концепции:**

- **Compute-storage separation** — данные в S3, вычислители (Spark, StarRocks) читают их независимо
- **Lakehouse** — open table format (Iceberg) поверх S3
- **Слои данных** — raw → staging → marts

---

## Архитектура

```
                        +----------------------------------+
                        |           AIRFLOW 2.10           |
                        |       (оркестрация DAG'ов)       |
                        +----------------+-----------------+
                                         |
              +--------------------------+--------------------------+
              v                          v                          v
      +---------------+          +---------------+          +---------------+
      |  data-init    |          |  Spark +      |          |  dbt run      |
      |  (генерация)  |          |  Iceberg      |          |  (модели)     |
      +-------+-------+          +-------+-------+          +-------+-------+
              |                          |                          |
              v                          v                          |
      +---------------------------------------+                     |
      |            MINIO (S3)                 |                     |
      |  raw CSV  |  warehouse (Parquet)      |                     |
      +------------------+--------------------+                     |
                         |                                          |
                         v                                          v
              +--------------------+                     +--------------------+
              |   ICEBERG REST     |<--------------------|    STARROCKS       |
              |   CATALOG          |                     |    (OLAP DWH)      |
              +--------------------+                     +----------+---------+
                                                                  |
                                                                  v
                                                       +--------------------+
                                                       |     SUPERSET       |
                                                       |     (BI / DASH)    |
                                                       +--------------------+
```

---

## Стек

| Компонент     | Версия                | Порт              | Назначение                 |
|---------------|-----------------------|-------------------|----------------------------|
| StarRocks     | 3.4 (allin1)          | 8030, 9030, 8040  | OLAP-база (MySQL-протокол) |
| MinIO         | latest (coollabsio)   | 9000, 9001        | S3-совместимое хранилище   |
| dbt           | 1.6.2 + dbt-starrocks | —                 | SQL-трансформации          |
| Superset      | 4.1.2                 | 8088              | BI и дашборды              |
| Airflow       | 2.10.5 (py3.11)       | 8080              | Оркестрация                |
| Spark         | 3.5.6                 | 4040, 8082, 10000 | ETL-движок                 |
| Iceberg REST  | 1.10.1 (fixture)      | 8181              | Каталог Iceberg-таблиц     |

---

## Структура проекта

```
dbt_sample/
├── .env                          # Переменные окружения
├── docker-compose.yml            # Все сервисы
├── start-airflow.ps1             # Запуск Airflow-режима
├── start-superset.ps1            # Запуск Superset-режима
├── start-all.ps1                 # Запуск всего (>=7 GB)
├── README.md
│
├── dbt/                          # Инфраструктура dbt
│   ├── Dockerfile
│   ├── README.md
│   ├── profiles/
│   │   └── profiles.yml
│   └── scripts/
│       ├── init.sh
│       ├── run_dbt.sh
│       ├── generate_and_upload.py   # Генерация -> S3
│       └── load_s3_to_starrocks.py  # S3 -> StarRocks
│
├── project/                      # dbt-проект
│   ├── dbt_project.yml
│   └── models/
│       ├── staging/              # 15 view-моделей
│       │   ├── sources.yml
│       │   └── stg_*.sql
│       └── marts/                # 6 table-моделей
│           ├── mart_*.sql
│           └── schema.yml
│
├── superset/                     # BI
│   ├── Dockerfile
│   ├── README.md
│   ├── requirements-local.txt
│   └── init/
│       ├── init-db.sh
│       ├── add_starrocks_db.py
│       └── create_dashboard.py
│
├── airflow/                      # Оркестрация
│   ├── Dockerfile
│   ├── README.md
│   ├── requirements.txt
│   └── dags/
│       ├── dbt_supply_chain_dag.py
│       └── spark_etl_dag.py
│
└── spark/                        # Lakehouse
    ├── README.md
    ├── conf/
    │   └── spark-defaults.conf
    ├── jobs/
    │   ├── etl_supply_chain.py
    │   └── verify_iceberg.py
    └── init-starrocks.sql
```

---

## Быстрый старт

### Требования

- **Docker Desktop** >= 4.30 (Windows / Mac) или Docker Engine (Linux)
- **Docker Compose** v2
- **ОЗУ**: минимум **8 ГБ** на хосте, рекомендуется **16 ГБ**
- **Диск**: ~15 ГБ

### Настройка памяти Docker (Windows)

В `.wslconfig` (Windows):

```ini
[wsl2]
memory=8GB
processors=4
swap=2GB
```

При 8 ГБ хоста — `memory=5GB` и работать по режимам.

Проверить:

```powershell
docker info | Select-String "Total Memory"
```

### Шаг 1. Настроить `.env`

```env
# StarRocks
STARROCKS_HOST=starrocks
STARROCKS_PORT=9030
STARROCKS_USER=root
STARROCKS_PASSWORD=
STARROCKS_SCHEMA=analytics
STARROCKS_CATALOG=default_catalog

# MinIO
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin
MINIO_ENDPOINT=http://minio:9000
MINIO_BUCKET=dbt-bucket
MINIO_REGION=us-east-1

# Данные
LAYER=stg
ROWS=5000
CHUNK_SIZE=2500
COLUMNS_PER_TABLE=120
WRITE_LOCAL=false
CLEAN_BEFORE_UPLOAD=false
BATCH_OFFSET=0

# Секреты
SUPERSET_SECRET_KEY=change_me_to_random_string
AIRFLOW_FERNET_KEY=8mX2rT9pLqK5vB1wYhN7jF3dC6sA0eU4xZbGqRkMnPc=
AIRFLOW__WEBSERVER__SECRET_KEY=airflow_secret_local
```

### Шаг 2. Запустить нужный режим

**Airflow-режим** (StarRocks + MinIO + dbt + Airflow):

```powershell
.\start-airflow.ps1
```

**Superset-режим** (StarRocks + MinIO + dbt + Superset):

```powershell
.\start-superset.ps1
```

**Всё сразу** (нужно >=7 ГБ Docker RAM):

```powershell
.\start-all.ps1
```

> На Windows PowerShell указывай `.\` перед именем скрипта. Если PowerShell ругается на политику — выполни один раз:
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
> ```

---

## Как всё устроено

### Data Flow

```
1. data-init
   - Генерация 15 CSV (5000 строк x ~120 колонок)
   - Загрузка в s3://dbt-bucket/stg/{table}/{date}/*.csv
   - Сохранение /tmp/_schema.json
   - Создание raw_{table} в StarRocks

2. dbt
   - dbt run  -> 15 stg views + 6 mart tables
   - dbt test -> 9 тестов

3. Spark ETL (опционально)
   - Читает CSV из s3a://dbt-bucket/stg/*/*.csv
   - Пишет Iceberg: lakehouse.supply_chain.{table}

4. StarRocks external catalog
   - Читает Iceberg через iceberg_lakehouse.{schema}.{table}

5. Superset
   - Дашборды поверх mart_* и Iceberg
```

### Слои данных

| Слой      | Где       | Формат          | Назначение            |
|-----------|-----------|-----------------|-----------------------|
| raw       | StarRocks | table           | Зеркало CSV           |
| staging   | StarRocks | view            | Лёгкая очистка        |
| marts     | StarRocks | table           | Аналитические витрины |
| lakehouse | MinIO     | Iceberg/Parquet | Open table format     |

### Ключевые принципы

1. **Разделение инфраструктуры и логики** — Dockerfile не равен моделям
2. **Compute-storage separation** — данные в S3, вычислители читают независимо
3. **Идемпотентность** — каждый шаг можно запустить дважды
4. **Модульность** — dbt/, superset/, airflow/, spark/ независимы

---

## Интерфейсы

| Сервис       | URL                     | Логин / пароль          |
|--------------|-------------------------|-------------------------|
| Airflow      | http://localhost:8080   | admin / admin           |
| Superset     | http://localhost:8088   | admin / admin           |
| MinIO        | http://localhost:9001   | minioadmin / minioadmin |
| StarRocks FE | http://localhost:8030   | root / (пусто)          |
| Spark UI     | http://localhost:4040   | —                       |

### Подключение из DBeaver к StarRocks

- Type: **MySQL**
- Host: `localhost`
- Port: `9030`
- User: `root`
- Password: *(пусто)*
- Database: `analytics`

---

## Полезные команды

### Запуск / остановка

```powershell
# Остановить всё
docker compose down

# Полный сброс (с данными)
docker compose down -v

# Запустить конкретный сервис
docker compose up -d starrocks minio

# Пересоздать с новыми volumes
docker compose up -d --force-recreate airflow-worker
```

### dbt

```powershell
docker compose run --rm --no-deps dbt dbt run
docker compose run --rm --no-deps dbt dbt test
docker compose run --rm --no-deps dbt dbt run --select stg_suppliers
docker compose run --rm --no-deps dbt dbt ls
```

### Spark

```powershell
# Spark SQL
docker exec -it spark_iceberg /opt/spark/bin/spark-sql

# ETL
docker exec -it spark_iceberg /opt/spark/bin/spark-submit /opt/spark/jobs/etl_supply_chain.py
```

### Airflow

```powershell
docker exec -it airflow_scheduler airflow dags list
docker exec -it airflow_scheduler airflow dags trigger dbt_supply_chain_pipeline
docker compose logs -f airflow-scheduler
```

### StarRocks (проверки)

```powershell
# Таблицы
docker exec starrocks mysql -h 127.0.0.1 -P 9030 -uroot -e "USE analytics; SHOW TABLES"

# Iceberg
docker exec starrocks mysql -h 127.0.0.1 -P 9030 -uroot -e "SHOW CATALOGS"
docker exec starrocks mysql -h 127.0.0.1 -P 9030 -uroot -e "SELECT COUNT(*) FROM iceberg_lakehouse.supply_chain.suppliers"
```

### Мониторинг

```powershell
docker compose ps
docker stats --no-stream
docker compose logs -f starrocks
```

---

## Troubleshooting

### Docker

| Ошибка                          | Решение                        |
|---------------------------------|--------------------------------|
| failed size validation при pull | Повторить docker pull 2–3 раза |
| cannot find the file specified  | Перезапустить Docker Desktop   |
| 500 Internal Server Error       | OOM — wsl --shutdown + перезапуск |

### StarRocks

| Ошибка                            | Решение                                    |
|-----------------------------------|--------------------------------------------|
| Cluster has no available capacity | Использовать allin1-ubuntu (FE+BE вместе)  |
| scheme is null в FILES()          | Грузить по одному файлу без wildcards      |
| Column 'X' is ambiguous           | Использовать ON a.col = b.col вместо USING |
| Insert has filtered data          | COALESCE(col, 'unknown') в CTE             |

### dbt

| Ошибка                                | Решение                                                       |
|---------------------------------------|---------------------------------------------------------------|
| CMySQLConnection object has no setter | dbt-core 1.6.2 + dbt-starrocks 1.6.2 + mysql-connector-python 8.0.22 |
| properties JSON error                 | properties='{...}' — строка, не dict                          |
| dbt: command not found в Airflow      | PATH=/home/airflow/.local/bin:... в env DAG                   |

### Spark

| Ошибка                                   | Решение                                                    |
|------------------------------------------|------------------------------------------------------------|
| FileNotFoundException: /home/spark/.ivy2 | spark.jars.ivy=/tmp/.ivy2                                  |
| ClassNotFoundException: S3AFileSystem    | Добавить hadoop-aws:3.3.4 + aws-java-sdk-bundle в packages |
| Maven долго качает                       | Первый запуск ~70 МБ, кэшируется                            |

### Память

`Exited (137)` = OOM.

- Увеличить `.wslconfig`: `memory=8GB` (при 16 ГБ хоста)
- Работать по режимам: `start-airflow.ps1` / `start-superset.ps1`
- Останавливать ненужное: `docker compose stop airflow-worker`

---

## Известные ограничения

| Ограничение           | Причина                       | Workaround                  |
|-----------------------|-------------------------------|-----------------------------|
| Память                | 4.8 ГБ Docker RAM             | Работа по режимам           |
| StarRocks healthcheck | Не задан в образе             | condition: service_started  |
| dbt-starrocks         | 1.6.2 — последняя стабильная  | Не обновлять до 1.7+        |
| Maven Spark           | Качается при первом запуске   | Кэш /tmp/.ivy2              |
| Iceberg REST fixture  | Не production-ready           | Для локальной разработки ок |

---

## Roadmap

### Сделано

- StarRocks + MinIO + dbt
- Superset с дашбордом Supply Chain Overview
- Airflow с DAG dbt_supply_chain_pipeline
- Spark + Iceberg + REST catalog
- External catalog StarRocks -> Iceberg
- 15 stg-моделей, 6 mart-моделей, 9 тестов

### Идеи

- Инкрементальный ETL — MERGE INTO вместо полной перезаписи
- CDC-пайплайн — симуляция потока изменений (I/U/D)
- Партиционирование Iceberg — по дате
- Iceberg compaction — устранение мелких файлов
- dbt поверх Iceberg — чтение lakehouse как source
- Scheduled reports в Superset
- Алерты в Telegram / Slack из Airflow
- Мониторинг Prometheus + Grafana
- CI/CD GitHub Actions
- IaC Terraform

---

## Полезные ссылки

- dbt Docs: https://docs.getdbt.com/
- Airflow Docs: https://airflow.apache.org/docs/
- StarRocks Docs: https://docs.starrocks.io/
- Iceberg Docs: https://iceberg.apache.org/docs/latest/
- Spark SQL Guide: https://spark.apache.org/docs/latest/sql-programming-guide.html
- MinIO Docs: https://min.io/docs/minio/linux/index.html
- Superset Docs: https://superset.apache.org/docs/intro

---

## Лицензия

Учебный проект. Компоненты под своими лицензиями:

| Компонент     | Лицензия   |
|---------------|------------|
| StarRocks     | Apache 2.0 |
| MinIO         | AGPL v3    |
| dbt-core      | Apache 2.0 |
| dbt-starrocks | Apache 2.0 |
| Superset      | Apache 2.0 |
| Airflow       | Apache 2.0 |
| Spark         | Apache 2.0 |
| Iceberg       | Apache 2.0 |

---

*Последнее обновление: октябрь 2026*