# AUDIT_REPORT.md — аудит проекта dbt_sample

**Дата аудита:** 2026-11-08  
**Аудитор:** DevOps-инженер (Kilo Code)  
**Статус:** аудит завершён, можно переходить к правкам.

---

## 1. Краткое резюме

Проект представляет собой локальный учебный lakehouse на Docker Compose:
Airflow 2.10.5, Spark 3.5.6 + Iceberg REST, MinIO, dbt 1.6.2 + dbt-starrocks,
StarRocks 3.4 allin1, Superset 4.1.2.

По коду и конфигам **Trino и Hive фактически отсутствуют**: единственное
упоминание — строка в документации `spark/README.md:328` («не Hive, не Glue»).
Однако в Docker-хосте **остались работающие контейнеры старой версии
docker-compose**: `trino`, `hive_metastore`, `hive_postgres` (project
`dbt_sample`, config file — текущий `docker-compose.yml`). Контейнер `trino`
занимает порт **8080**, из-за чего Airflow webserver не сможет стартовать.
Это критичный блокер, который нужно устранить до запуска стека.

Дополнительно обнаружен разрыв между README и фактическим состоянием:
в проекте есть MOEX-модели и скрипты (16-я staging-модель и 7-я mart-модель),
при этом `generate_and_upload.py` при каждом запуске удаляет **все**
`stg_*.sql` и перезаписывает `sources.yml` только 15 таблицами. В результате
`stg_moex_prices.sql` исчезает, а `mart_moex_daily_returns.sql` остаётся и
ломает `dbt run`. Это нужно исправить, чтобы пайплайн был воспроизводимым.

---

## 2. Структура проекта

```
dbt_sample/
├── .env
├── docker-compose.yml
├── README.md
├── make_dag.py                    # генератор DAG (служебный)
├── make_stg.ps1                   # пустой файл (0 байт)
├── setup_starrocks.py             # генератор файлов проекта (служебный)
├── start-airflow.ps1
├── start-all.ps1
├── start-superset.ps1
│
├── airflow/
│   ├── Dockerfile
│   ├── README.md
│   └── dags/
│       └── dbt_supply_chain_dag.py
│
├── dbt/
│   ├── Dockerfile
│   ├── README.md
│   ├── profiles/
│   │   ├── profiles.yml
│   │   └── .user.yml
│   └── scripts/
│       ├── init.sh
│       ├── run_dbt.sh
│       ├── generate_and_upload.py
│       ├── load_s3_to_starrocks.py
│       ├── load_moex_to_s3.py
│       ├── load_moex_to_starrocks.sql
│       └── create_moex_table.sql
│
├── project/                       # dbt-проект
│   ├── dbt_project.yml
│   ├── logs/
│   ├── target/                    # артефакты прошлых запусков
│   └── models/
│       ├── staging/
│       │   ├── sources.yml
│       │   ├── stg_*.sql          # 16 файлов (15 supply chain + MOEX)
│       └── marts/
│           ├── schema.yml
│           └── mart_*.sql         # 7 файлов (6 supply chain + MOEX)
│
├── spark/
│   ├── README.md
│   ├── conf/spark-defaults.conf
│   ├── jobs/etl_supply_chain.py
│   └── init-starrocks.sql
│
└── superset/
    ├── Dockerfile
    ├── README.md
    ├── requirements-local.txt
    └── init/
        ├── init-db.sh
        ├── add_starrocks_db.py
        └── create_dashboard.py
```

---

## 3. Сервисы и назначение

### 3.1 Сервисы в фактическом `docker-compose.yml`

| Сервис | Образ / сборка | Назначение | Порты | Healthcheck |
|---|---|---|---|---|
| `starrocks` | `starrocks/allin1-ubuntu:3.4-latest` | OLAP DWH, FE+BE в одном контейнере | 8030, 9030, 8040 | нет (condition: service_started) |
| `minio` | `ghcr.io/coollabsio/minio:latest` | S3-хранилище | 9000, 9001 | `mc ready local` |
| `data-init` | `./dbt/Dockerfile` | Генерация CSV → MinIO → StarRocks | — | нет (one-shot) |
| `dbt` | `./dbt/Dockerfile` | `dbt debug/run/test` | — | нет (one-shot) |
| `superset` | `./superset/Dockerfile` | BI webserver (gunicorn) | 8088 | нет |
| `superset-init` | `./superset/Dockerfile` | Миграции, админ, подключение StarRocks | — | нет (one-shot) |
| `superset-worker` | `./superset/Dockerfile` | Celery worker Superset | — | нет |
| `postgres-airflow` | `postgres:15-alpine` | Метаданные Airflow | — | `pg_isready` |
| `redis` | `redis:7-alpine` | Celery broker | 6379 (expose) | `redis-cli ping` |
| `airflow-init` | `./airflow/Dockerfile` | Миграции БД Airflow + admin | — | нет (one-shot) |
| `airflow-webserver` | `dbt_sample-airflow:latest` | Airflow UI | 8080 | `curl /health` |
| `airflow-scheduler` | `dbt_sample-airflow:latest` | Планировщик DAG | — | нет |
| `airflow-worker` | `dbt_sample-airflow:latest` | Celery worker | — | `celery inspect ping` |
| `airflow-triggerer` | `dbt_sample-airflow:latest` | Triggerer | — | нет |
| `iceberg-rest` | `apache/iceberg-rest-fixture:1.10.1` | Iceberg REST catalog | 8181 | нет |
| `spark-iceberg` | `apache/spark:3.5.6` | Spark ETL (контейнер живёт через `tail -f`) | 8888, 8082→8080, 10000, 4040 | нет |

### 3.2 Сервисы, которых нет в compose, но которые реально запущены

| Контейнер | Образ | Статус | Проблема |
|---|---|---|---|
| `trino` | `trinodb/trino:481` | Up (healthy), порт 8080 | Занимает порт Airflow, остаток старой версии compose |
| `hive_metastore` | `apache/hive:4.0.0` | Up, порт 9083 | Остаток старой версии compose |
| `hive_postgres` | `postgres:15-alpine` | Up (healthy) | Остаток старой версии compose |

Все три контейнера имеют метки:
`com.docker.compose.project=dbt_sample`,
`com.docker.compose.project.config_files=C:\Users\opir1\Documents\dbt_sample\docker-compose.yml`.
То есть это «сироты» (orphans) от предыдущей версии compose-файла.

---

## 4. Текущее состояние docker-compose

- `docker compose config` валиден, ошибок YAML нет.
- Проект Compose: `dbt_sample`.
- Сеть: одна bridge-сеть `dbt_network`.
- Volumes: `starrocks_data`, `minio_data`, `superset_home`, `postgres_airflow_data`.
- Явных конфликтов внутри compose нет.
- **Внешний конфликт:** порт 8080 занят контейнером `trino` из старого compose.
- `spark-iceberg` не имеет healthcheck и не запускает Spark-сервисы (master/worker/thrift);
  контейнер держится `tail -f /dev/null`, команды подаются через `docker exec`.
- `iceberg-rest` не имеет healthcheck и не зависит от `minio` (формально
  `spark-iceberg` зависит от обоих, но сам catalog может стартовать раньше MinIO).
- `airflow-webserver`, `airflow-scheduler`, `airflow-worker`, `airflow-triggerer`
  используют образ `dbt_sample-airflow:latest`, который собирается в сервисе
  `airflow-init`. Остальные сервисы Airflow **не имеют `build:`**, поэтому при
  `docker compose up --build` образ должен быть собран через `airflow-init`.
  Это работает, но хрупко: если `airflow-init` не попадёт в выборку, образ
  может отсутствовать.

---

## 5. Упоминания Trino/Hive

### 5.1 Поиск по проекту

Использованная команда (аналог на PowerShell):

```powershell
Get-ChildItem -Recurse -File |
  Where-Object { $_.FullName -notmatch '\\\.git\\' } |
  Select-String -Pattern 'trino|hive' -CaseSensitive:$false
```

Результат:

| Файл | Строка | Контекст | Влияние |
|---|---|---|---|
| `spark/README.md` | 328 | `REST-каталог (не Hive, не Glue)` | Только документация; функционального влияния нет, но по требованиям должно быть удалено |

**В коде, docker-compose, Dockerfile, .env, requirements, profiles,
sources.yml, DAG, init-скриптах, SQL и остальных README упоминаний
Trino/Hive не найдено.**

### 5.2 Упоминания в Docker-окружении (не в файлах проекта)

| Объект | Тип | Влияние |
|---|---|---|
| `trino` (`trinodb/trino:481`) | запущенный контейнер | Занимает 8080 → Airflow webserver не стартует |
| `hive_metastore` (`apache/hive:4.0.0`) | запущенный контейнер | Лишний сервис, остаток старой архитектуры |
| `hive_postgres` (`postgres:15-alpine`) | запущенный контейнер | Лишний сервис, метастор Hive |
| `trinodb/trino:481` | Docker image | Остаток, можно удалить после контейнеров |
| `apache/hive:4.0.0`, `apache/hive:3.1.3` | Docker images | Остатки, можно удалить после контейнеров |

Эти объекты не описаны в текущем `docker-compose.yml`, но продолжают жить
в Docker daemon и мешают запуску проекта.

---

## 6. Отличия фактического состояния от README

| README | Фактически | Влияние |
|---|---|---|
| 15 staging-моделей | 16 (`stg_moex_prices.sql` дополнительно) | `generate_and_upload.py` удаляет все `stg_*.sql`, включая MOEX |
| 6 mart-моделей | 7 (`mart_moex_daily_returns.sql` дополнительно) | После регенерации staging ссылается на удалённую `stg_moex_prices` → `dbt run` падает |
| `airflow/requirements.txt` | файла нет | README ссылается на несуществующий файл; зависимости ставятся в Dockerfile |
| `airflow/dags/spark_etl_dag.py` | файла нет | README описывает DAG, которого нет |
| `spark/jobs/verify_iceberg.py` | файла нет | README и план проверки ссылаются на несуществующий скрипт |
| dbt test = 9 | 9 тестов для 6 mart-моделей; у MOEX-модели тестов нет | Ожидаемое число тестов сохраняется |
| `.env` без MOEX | в `.env` есть `MOEX_*` | MOEX-функциональность не описана в README |
| `profiles.yml` без `use_pure` | в `profiles.yml` есть `use_pure: "true"` | README прямо говорит, что параметр не поддерживается; риск ошибки подключения |
| Trino/Hive не упоминаются | в Docker запущены trino/hive из старого compose | Критичный конфликт порта 8080 |

---

## 7. Зависимости, порты, volumes, networks, healthcheck

### 7.1 Порты

| Порт | Сервис | Статус |
|---|---|---|
| 8030 | StarRocks FE HTTP | заявлен |
| 9030 | StarRocks MySQL protocol | заявлен |
| 8040 | StarRocks BE | заявлен |
| 9000 | MinIO S3 API | заявлен |
| 9001 | MinIO Console | заявлен |
| 8080 | Airflow webserver | **занят старым контейнером `trino`** |
| 8088 | Superset | заявлен |
| 8181 | Iceberg REST | заявлен |
| 4040 | Spark UI | заявлен |
| 8082 → 8080 | Spark Master UI (фактически master не запущен) | заявлен |
| 10000 | Spark Thrift Server (фактически не запущен) | заявлен |
| 8888 | Jupyter (фактически не запущен) | заявлен |
| 6379 | Redis | только внутри сети (expose) |

### 7.2 Volumes

| Volume | Используется | Назначение |
|---|---|---|
| `starrocks_data` | `starrocks` | Данные StarRocks |
| `minio_data` | `minio` | Объекты S3 |
| `superset_home` | `superset`, `superset-init`, `superset-worker` | Метаданные Superset (SQLite) |
| `postgres_airflow_data` | `postgres-airflow` | Метаданные Airflow |

### 7.3 Networks

- `dbt_network` (bridge) — единственная сеть, все сервисы подключены.
- Внутренние имена: `starrocks`, `minio`, `iceberg-rest`, `postgres-airflow`, `redis`.

### 7.4 Healthcheck

| Сервис | Healthcheck | Комментарий |
|---|---|---|
| `minio` | `mc ready local` | рабочий |
| `postgres-airflow` | `pg_isready` | рабочий |
| `redis` | `redis-cli ping` | рабочий |
| `airflow-webserver` | `curl /health` | зависит от наличия curl в образе |
| `airflow-worker` | `celery inspect ping` | рабочий при корректном hostname |
| `starrocks` | нет | известное ограничение README |
| `iceberg-rest` | нет | известное ограничение |
| `spark-iceberg` | нет | контейнер-держатель |

---

## 8. Конфиги

### 8.1 Airflow

- `airflow/Dockerfile`: `apache/airflow:2.10.5-python3.11`,
  ставит `apache-airflow-providers-common-sql`, `astronomer-cosmos`,
  `dbt-core==1.6.2`, `dbt-starrocks==1.6.2`, `pandas`, `requests`,
  `mysql-connector-python==8.0.33`.
- **Не ставит явно `boto3` и `pymysql`**, хотя DAG запускает скрипты,
  которые их импортируют. Риск: `ModuleNotFoundError` в задачах
  `generate_and_upload` / `load_to_starrocks`.
- `dbt_supply_chain_dag.py`: 4 задачи —
  `generate_and_upload → load_to_starrocks → dbt_run → dbt_test`.
  Использует `BashOperator`, env с StarRocks/MinIO. Trino/Hive connections
  не используются.
- `airflow-init` использует `command: version` + `_AIRFLOW_DB_MIGRATE` /
  `_AIRFLOW_WWW_USER_CREATE` — штатный паттерн Airflow.

### 8.2 dbt

- `dbt/Dockerfile`: Python 3.11, `dbt-core==1.6.2`, `dbt-starrocks==1.6.2`,
  `pymysql`, `boto3`, `pandas`, `requests`, `mysql-connector-python==8.0.33`.
- `profiles.yml`: StarRocks, host `starrocks`, schema `analytics`,
  `catalog: default_catalog`, `version: 3.4.0`, `use_pure: "true"`.
  Параметр `use_pure` противоречит README и может ломать подключение.
- `project/dbt_project.yml`: staging → view, marts → table.
- `sources.yml`: 15 raw-таблиц (без `raw_moex_prices`).
- `marts/schema.yml`: 9 тестов для 6 mart-моделей.
- MOEX-модели:
  - `stg_moex_prices.sql` читает `source('raw', 'raw_moex_prices')`;
  - `mart_moex_daily_returns.sql` читает `ref('stg_moex_prices')`;
  - `generate_and_upload.py` при запуске удаляет **все** `stg_*.sql` и
    создаёт только 15 моделей, после чего `stg_moex_prices.sql` исчезает;
  - `sources.yml` перезаписывается без `raw_moex_prices`;
  - `raw_moex_prices` не создаётся в `load_s3_to_starrocks.py`.

### 8.3 Spark + Iceberg

- `spark/conf/spark-defaults.conf`:
  - каталог `lakehouse`, type `rest`, URI `http://iceberg-rest:8181`;
  - warehouse `s3://dbt-bucket/warehouse`;
  - S3FileIO, MinIO endpoint, path-style access;
  - Maven-пакеты Iceberg 1.4.3, hadoop-aws 3.3.4, aws-java-sdk-bundle 1.12.262;
  - Ivy cache `/tmp/.ivy2`;
  - лимиты памяти 512m.
- `spark/jobs/etl_supply_chain.py` читает
  `s3a://dbt-bucket/stg/suppliers/*/*.csv` и пишет
  `lakehouse.supply_chain.suppliers`.
- `spark/jobs/verify_iceberg.py` **отсутствует**, хотя заявлен в README.
- `spark/init-starrocks.sql` создаёт external catalog `iceberg_lakehouse`
  типа `iceberg` с REST URI `http://iceberg-rest:8181`.

### 8.4 Superset

- `superset/Dockerfile`: `apache/superset:4.1.2`, системные зависимости,
  `starrocks==1.0.6`, `mysqlclient`.
- `init-db.sh`: ждёт StarRocks, выполняет `superset db upgrade`,
  создаёт admin/admin, `superset init`, добавляет подключение StarRocks.
- `add_starrocks_db.py`: URI
  `starrocks://root:@starrocks:9030/default_catalog.analytics?charset=utf8`.
- `superset-worker` использует Celery без явного broker URL — риск
  бесконечных рестартов, если Superset не настроен на Redis/SQLite broker.

### 8.5 StarRocks

- `starrocks` allin1, TZ=UTC, volume `starrocks_data`, без healthcheck.
- `init-starrocks.sql` — external catalog `iceberg_lakehouse`.
- `load_s3_to_starrocks.py` создаёт `analytics.raw_*` и грузит CSV через `FILES()`.

### 8.6 MinIO / Iceberg REST

- MinIO: bucket `dbt-bucket` создаётся генератором; healthcheck `mc ready local`.
- Iceberg REST: `CATALOG_WAREHOUSE=s3://dbt-bucket/warehouse`,
  S3FileIO, endpoint `http://minio:9000`, path-style.
- `iceberg-rest` не имеет `depends_on: minio`; при старте может кратковременно
  получить ошибку S3, но обычно повторяет запросы.

---

## 9. Текущие проблемы и риски

### Критичные

1. **Порт 8080 занят контейнером `trino`** из старого compose.
   Airflow webserver не сможет забиндиться.
2. **Остатки Trino/Hive в Docker**: `trino`, `hive_metastore`, `hive_postgres`,
   images `trinodb/trino:481`, `apache/hive:4.0.0`, `apache/hive:3.1.3`.
3. **MOEX-модель ломает dbt**: `generate_and_upload.py` удаляет
   `stg_moex_prices.sql`, но `mart_moex_daily_returns.sql` остаётся.
   После `data-init` `dbt run` завершится ошибкой компиляции.
4. **В образе Airflow могут отсутствовать `boto3` и `pymysql`**,
   необходимые задачам DAG. Нужно проверить в контейнере.

### Средние

5. `profiles.yml` содержит `use_pure: "true"`, хотя README говорит,
   что параметр не поддерживается.
6. `spark/jobs/verify_iceberg.py` отсутствует, но используется в плане
   проверки и README.
7. `airflow/dags/spark_etl_dag.py` отсутствует, хотя README его описывает.
8. `airflow/requirements.txt` отсутствует, хотя README его описывает.
9. `superset-worker` может рестартовать из-за отсутствия broker URL.
10. `spark-iceberg` не имеет зависимости по здоровью от `iceberg-rest`
    и `minio` (только `depends_on` без condition).
11. `airflow-webserver` healthcheck зависит от `curl`; нужно проверить.
12. `airflow-init` — единственный сервис Airflow с `build:`; остальные
    используют `image: dbt_sample-airflow:latest`. При выборочном запуске
    образ может отсутствовать.

### Некритичные

13. `make_stg.ps1` — пустой файл.
14. `setup_starrocks.py` содержит устаревшую конфигурацию (FE/BE раздельно,
    dbt 1.9.0) и не соответствует текущему compose. Это служебный генератор,
    на запуск не влияет.
15. В `project/target/` лежат артефакты старых моделей
    (`mart_customer_orders`, `stg_customers`, `stg_orders` и т.п.),
    не относящихся к текущему проекту.
16. `.env` содержит дубли `AIRFLOW_FERNET_KEY` и
    `AIRFLOW__WEBSERVER__SECRET_KEY`.

---

## 10. План правок

1. **Удалить остатки Trino/Hive из Docker:**
   - остановить и удалить контейнеры `trino`, `hive_metastore`, `hive_postgres`;
   - удалить images `trinodb/trino:481`, `apache/hive:4.0.0`,
     `apache/hive:3.1.3` (если не используются другими проектами);
   - проверить, что порт 8080 свободен.
2. **Удалить единственное упоминание Hive в документации:**
   - `spark/README.md:328` — переформулировать без Hive.
3. **Исправить MOEX-регрессию, не удаляя пользовательскую функциональность:**
   - `generate_and_upload.py` не должен удалять `stg_moex_prices.sql`;
   - `sources.yml` должен содержать `raw_moex_prices`;
   - `load_s3_to_starrocks.py` должен создавать пустую таблицу
     `raw_moex_prices`, если её нет (чтобы `dbt run` не падал без MOEX-загрузки).
4. **Исправить Airflow-образ:**
   - добавить `boto3`, `botocore`, `pymysql` в `airflow/Dockerfile`
     (если их нет в базовом образе).
5. **Исправить `profiles.yml`:** убрать `use_pure`, если подключение
   не работает (проверить `dbt debug`).
6. **Добавить минимально необходимые проверки/файлы:**
   - `spark/jobs/verify_iceberg.py` для проверки Iceberg (если нужен по README);
   - при необходимости — `spark_etl_dag.py` (только если это не ломает
     заявленный набор DAG; иначе зафиксировать отсутствие в отчёте).
7. **Запустить стек:**
   - `docker compose down --remove-orphans`;
   - `docker compose up -d --build`;
   - `docker compose ps`;
   - проверить логи проблемных сервисов.
8. **Проверить интеграции:**
   - MinIO bucket `dbt-bucket` и CSV;
   - dbt `debug/deps/run/test` (15+6/9 или 16+7/9 — зафиксировать факт);
   - Spark ETL + Iceberg;
   - StarRocks `SHOW CATALOGS` и SELECT из `iceberg_lakehouse`;
   - Superset UI 8088;
   - Airflow DAG list / trigger.
9. **Повторно выполнить grep по Trino/Hive** — должно быть пусто
   (кроме отчётов).
10. **Записать результаты в `REPORT_DOCKER_FIX.md`.**

---

## 11. Явная пометка

**Аудит завершён. Можно переходить к правкам.**
