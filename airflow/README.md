# airflow — оркестрация пайплайнов

Модуль отвечает за **планирование и запуск** data-пайплайнов.
Airflow координирует шаги: генерация данных → загрузка в S3 → dbt трансформации
→ тесты. Также может запускать Spark ETL.

Airflow запускает bash-команды **внутри своих контейнеров**, обращаясь
к StarRocks, MinIO, dbt через общую сеть `dbt_network`.

---

## Структура

    airflow/
    ├── README.md                        # Этот файл
    ├── Dockerfile                       # Образ Airflow + dbt + cosmos
    ├── requirements.txt                 # Дополнительные pip-пакеты
    └── dags/
        ├── dbt_supply_chain_dag.py      # Основной DAG пайплайна
        └── spark_etl_dag.py             # DAG для Spark ETL (опционально)

---

## Зачем это нужно

Модуль решает три задачи:

1. **Сборка окружения** — образ Airflow с dbt и вспомогательными библиотеками.
2. **Оркестрация** — последовательный запуск шагов пайплайна.
3. **Расписание** — автоматический запуск по cron-выражению.

Что даёт Airflow:

- **DAG** — граф зависимостей между задачами (task dependencies).
- **Scheduler** — следит за расписанием, запускает DAG'и.
- **Retries** — автоматические повторы упавших задач.
- **Logs & UI** — визуализация статуса, логов, истории.
- **Backfill** — перезапуск прошлых запусков.
- **SLA & alerts** — уведомления о нарушениях.

---

## Архитектура

    +-----------------------+
    |      Scheduler        |  ← следит за расписанием
    +----------+------------+
               |
               v
    +-----------------------+
    |    Redis (broker)     |  ← очередь задач
    +----------+------------+
               |
               v
    +-----------------------+
    |    Worker (Celery)    |  ← выполняет bash-команды
    +----------+------------+
               |
               v
    +-----------------------+
    |      StarRocks        |  ← источник / цель данных
    |      MinIO            |
    |      Spark            |
    +-----------------------+
               ^
               |
    +-----------------------+
    |    Webserver (UI)     |  ← графический интерфейс
    +-----------------------+
               ^
               |
    +-----------------------+
    |   Postgres (metadata) |  ← история запусков
    +-----------------------+

**Компоненты в docker-compose:**

| Сервис           | Роль                                                     |
|------------------|----------------------------------------------------------|
| postgres-airflow | Метаданные Airflow (DAG'и, runs, connections)            |
| redis            | Брокер Celery (очередь задач)                             |
| airflow-init     | Одноразовый: миграции БД + создание админа                |
| airflow-webserver| Web UI на порту 8080                                      |
| airflow-scheduler| Планировщик DAG'ов                                        |
| airflow-worker   | Выполняет задачи через Celery                             |
| airflow-triggerer| Deferred operators (async)                                |

---

## Dockerfile

**Базовый образ:** apache/airflow:2.10.5-python3.11

**Что устанавливается:**

| Пакет                          | Зачем                                              |
|--------------------------------|----------------------------------------------------|
| dbt-core==1.6.2                | Тот же dbt, что в модуле `dbt/`                    |
| dbt-starrocks==1.6.2           | Адаптер StarRocks                                  |
| mysql-connector-python==8.0.22 | Драйвер БД (единственная версия без бага)          |
| astronomer-cosmos              | Опционально: запуск dbt-моделей как Airflow-задач |
| boto3, pandas, requests        | Для скриптов генерации и загрузки                  |

**Почему Python 3.11, а не 3.12:**

`dbt-core==1.6.2` не собирается на Python 3.12. В образе
`apache/airflow:2.10.5` по умолчанию Python 3.12 — поэтому используем
тег `-python3.11`.

**Почему тот же dbt, что в `dbt/`:**

Airflow выполняет команды `dbt run`, `dbt test` внутри своего worker'а.
Библиотеки должны быть **совместимы** с теми, что в `dbt/Dockerfile`.

**Критичные моменты:**

1. **Версии dbt зафиксированы** — иначе pip подтянет несовместимый
   `mysql-connector-python` и сломает подключение.

2. **`mysql-connector-python==8.0.22` ставится через `--force-reinstall --no-deps`** —
   dbt-starrocks требует `>=8.1`, но версия 8.0.22 — единственная без бага
   `server_version`. Форсируем установку.

3. **Зеркало PyPI** — Tsinghua для скорости из РФ.

4. **Один образ для всех сервисов Airflow** — webserver, scheduler, worker
   должны видеть **одни и те же** DAG'и и библиотеки.

**Рабочая директория:** `/opt/airflow` (стандарт для официального образа).

---

## requirements.txt

**Назначение:** список pip-пакетов, которые ставятся в образ.

**Содержимое (пример):**

    apache-airflow-providers-common-sql
    astronomer-cosmos

**Почему отдельным файлом:**

- Легко добавлять/убирать зависимости без правки Dockerfile.
- Можно копировать как есть из официального репозитория.
- Всё, что явно видно — легче версионировать.

**Может отсутствовать**, если всё ставится прямо в Dockerfile.

---

## dags/dbt_supply_chain_dag.py

**Назначение:** главный DAG пайплайна.

**Структура:**

    generate_and_upload  →  load_to_starrocks  →  dbt_run  →  dbt_test

**Полный код:**

    from datetime import datetime

    from airflow import DAG
    from airflow.operators.bash import BashOperator

    ENV = {
        "PATH": "/home/airflow/.local/bin:/usr/local/bin:/usr/bin:/bin",
        "STARROCKS_HOST": "starrocks",
        "STARROCKS_PORT": "9030",
        "STARROCKS_USER": "root",
        "STARROCKS_PASSWORD": "",
        "STARROCKS_SCHEMA": "analytics",
        "STARROCKS_CATALOG": "default_catalog",
        "MINIO_ENDPOINT": "http://minio:9000",
        "MINIO_ROOT_USER": "minioadmin",
        "MINIO_ROOT_PASSWORD": "minioadmin",
        "MINIO_BUCKET": "dbt-bucket",
        "MINIO_REGION": "us-east-1",
        "LAYER": "stg",
        "ROWS": "5000",
        "CHUNK_SIZE": "2500",
        "COLUMNS_PER_TABLE": "120",
        "WRITE_LOCAL": "false",
        "SCHEMA_JSON_PATH": "/tmp/_schema.json",
        "DBT_PROJECT_DIR": "/opt/airflow/dbt_project",
        "DBT_PROFILES_DIR": "/opt/airflow/dbt_profiles",
    }

    default_args = {
        "owner": "data-team",
        "retries": 0,
    }

    with DAG(
        dag_id="dbt_supply_chain_pipeline",
        description="Generaciya -> S3 -> StarRocks -> dbt",
        default_args=default_args,
        start_date=datetime(2026, 1, 1),
        schedule="0 3 * * *",
        catchup=False,
        max_active_runs=1,
        tags=["dbt", "starrocks"],
    ) as dag:

        gen = BashOperator(
            task_id="generate_and_upload",
            bash_command="python /opt/airflow/dbt/scripts/generate_and_upload.py",
            env=ENV,
        )

        load = BashOperator(
            task_id="load_to_starrocks",
            bash_command="python /opt/airflow/dbt/scripts/load_s3_to_starrocks.py",
            env=ENV,
        )

        run = BashOperator(
            task_id="dbt_run",
            bash_command=(
                "mkdir -p /tmp/dbt_logs /tmp/dbt_target && "
                "cd /opt/airflow/dbt_project && "
                "dbt --log-path /tmp/dbt_logs run "
                "--profiles-dir /opt/airflow/dbt_profiles "
                "--target-path /tmp/dbt_target"
            ),
            env=ENV,
        )

        test = BashOperator(
            task_id="dbt_test",
            bash_command=(
                "mkdir -p /tmp/dbt_logs /tmp/dbt_target && "
                "cd /opt/airflow/dbt_project && "
                "dbt --log-path /tmp/dbt_logs test "
                "--profiles-dir /opt/airflow/dbt_profiles "
                "--target-path /tmp/dbt_target"
            ),
            env=ENV,
        )

        gen >> load >> run >> test

**Пошаговое описание:**

| Строка                              | Что делает                                              |
|-------------------------------------|--------------------------------------------------------|
| `from airflow import DAG`           | Импорт класса DAG                                       |
| `from airflow.operators.bash import BashOperator` | Оператор для запуска bash-команд         |
| `ENV = {...}`                       | Переменные, передаваемые в задачи                       |
| `default_args = {owner, retries}`   | Настройки по умолчанию для всех задач                   |
| `with DAG(...) as dag:`             | Контекстный менеджер — создаёт DAG                      |
| `dag_id="..."`                      | Уникальный идентификатор                                |
| `schedule="0 3 * * *"`              | Расписание: каждый день в 03:00 UTC                     |
| `catchup=False`                     | Не запускать пропущенные даты при первом включении      |
| `max_active_runs=1`                 | Не более одного параллельного запуска                   |
| `BashOperator(...)`                 | Задача, запускающая bash-команду                         |
| `env=ENV`                           | Переменные окружения для команды                        |
| `gen >> load >> run >> test`        | Порядок выполнения                                      |

**Ключевые переменные `ENV`:**

| Переменная           | Значение                     | Зачем                                              |
|----------------------|------------------------------|-----------------------------------------------------|
| PATH                 | `/home/airflow/.local/bin:...` | Чтобы `dbt` находился (он ставится в `.local/bin`) |
| STARROCKS_HOST       | `starrocks`                  | Имя сервиса в docker-сети                           |
| MINIO_ENDPOINT       | `http://minio:9000`          | Endpoint MinIO                                      |
| SCHEMA_JSON_PATH     | `/tmp/_schema.json`          | Куда писать схему (не в `/dbt`, там нет прав)      |
| DBT_PROJECT_DIR      | `/opt/airflow/dbt_project`   | Где искать dbt-модели                               |
| DBT_PROFILES_DIR     | `/opt/airflow/dbt_profiles`  | Где искать `profiles.yml`                           |

**Почему `--log-path /tmp/dbt_logs`:**

По умолчанию dbt пишет `logs/dbt.log` в папку проекта. Но папка `/dbt_project`
смонтирована **только для чтения** в контейнере Airflow — попытка записи даёт
`PermissionError`. Решение — писать во временный `/tmp`.

**Почему `--target-path /tmp/dbt_target`:**

Аналогично — скомпилированные модели не должны писаться в read-only volume.

**Почему `retries: 0`:**

Для отладки — чтобы падало сразу, без ожидания. В production обычно ставят
`retries: 2` с `retry_delay: timedelta(minutes=5)`.

**Как изменить расписание:**

- `schedule="0 3 * * *"` — каждый день в 3:00 UTC.
- `schedule="0 */6 * * *"` — каждые 6 часов.
- `schedule="0 0 * * 1"` — по понедельникам.
- `schedule=None` — только ручной запуск.

**Формат cron:** `minute hour day_of_month month day_of_week`.

---

## dags/spark_etl_dag.py (опционально)

**Назначение:** отдельный DAG для запуска Spark ETL.

**Код:**

    from datetime import datetime
    from airflow import DAG
    from airflow.operators.bash import BashOperator

    default_args = {
        "owner": "data-team",
        "retries": 0,
    }

    with DAG(
        dag_id="spark_etl_pipeline",
        description="Spark ETL -> Iceberg -> StarRocks",
        default_args=default_args,
        start_date=datetime(2026, 1, 1),
        schedule="0 */6 * * *",
        catchup=False,
        tags=["spark", "iceberg"],
    ) as dag:

        spark_etl = BashOperator(
            task_id="spark_etl_incremental",
            bash_command=(
                "docker exec spark_iceberg "
                "/opt/spark/bin/spark-submit /opt/spark/jobs/etl_supply_chain.py"
            ),
        )

**Особенность:** Airflow-worker не умеет запускать `docker exec` в других
контейнерах по умолчанию. Нужно **смонтировать docker.sock**:

    airflow-worker:
      volumes:
        ...
        - /var/run/docker.sock:/var/run/docker.sock

Это даёт контейнеру доступ к Docker-демону хоста — но **это потенциальный
риск безопасности**. Для учебного проекта допустимо, для production — нет.

**Альтернатива:** использовать `SparkSubmitOperator` из `apache-airflow-providers-apache-spark`,
но он требует отдельного Spark-кластера с REST API.

---

## Как это связано с docker-compose

Сервис `postgres-airflow`:

    postgres-airflow:
      image: postgres:15-alpine
      environment:
        - POSTGRES_USER=airflow
        - POSTGRES_PASSWORD=airflow
        - POSTGRES_DB=airflow
      volumes: [postgres_airflow_data:/var/lib/postgresql/data]

Хранит **метаданные** Airflow:
- DAG-файлы (парсинг, хеши).
- Task instances (статусы, время).
- Connections (пароли шифруются).
- Variables.
- XCom (обмен данными между задачами).

**Почему отдельный Postgres:**

Метаданные Airflow — это **не аналитические данные**. Они не должны
лежать в StarRocks — разные задачи и разный профиль нагрузки.

Сервис `redis`:

    redis:
      image: redis:7-alpine
      expose: [6379]

Celery-брокер. Scheduler кладёт сюда задачи, worker'ы забирают.

**Почему Redis, а не RabbitMQ:**

Redis проще, легче, достаточно для большинства задач. RabbitMQ — для очень
больших нагрузок (не наш случай).

Сервис `airflow-init` (одноразовый):

    airflow-init:
      build: { context: ./airflow, dockerfile: Dockerfile }
      image: dbt_sample-airflow:latest
      environment:
        - AIRFLOW__CORE__EXECUTOR=CeleryExecutor
        - AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://airflow:airflow@postgres-airflow/airflow
        - AIRFLOW__CELERY__RESULT_BACKEND=db+postgresql://airflow:airflow@postgres-airflow/airflow
        - AIRFLOW__CELERY__BROKER_URL=redis://redis:6379/0
        - AIRFLOW__CORE__FERNET_KEY=${AIRFLOW_FERNET_KEY}
        - _AIRFLOW_DB_MIGRATE=true
        - _AIRFLOW_WWW_USER_CREATE=true
        - _AIRFLOW_WWW_USER_USERNAME=admin
        - _AIRFLOW_WWW_USER_PASSWORD=admin
      command: version

**Ключевые переменные:**

| Переменная                         | Что делает                                          |
|------------------------------------|-----------------------------------------------------|
| EXECUTOR=CeleryExecutor            | Использовать Celery (Redis + workers)               |
| SQL_ALCHEMY_CONN                   | Где хранятся метаданные                             |
| RESULT_BACKEND                     | Куда worker'ы пишут результаты                      |
| BROKER_URL                         | Redis как очередь                                   |
| FERNET_KEY                         | Ключ шифрования паролей connections                 |
| _AIRFLOW_DB_MIGRATE=true           | Автомиграции при старте                             |
| _AIRFLOW_WWW_USER_CREATE=true      | Автосоздание админа                                 |
| _AIRFLOW_WWW_USER_USERNAME=admin   | Логин админа                                        |
| _AIRFLOW_WWW_USER_PASSWORD=admin   | Пароль админа                                       |
| command: version                   | Ничего не делать, только миграции и админ           |

Сервис `airflow-webserver`:

    airflow-webserver:
      image: dbt_sample-airflow:latest
      ports: ["8080:8080"]
      command: webserver
      volumes:
        - ./airflow/dags:/opt/airflow/dags
        - ./airflow/logs:/opt/airflow/logs
        - ./airflow/plugins:/opt/airflow/plugins
        - ./airflow/config:/opt/airflow/config
        - ./dbt/scripts:/opt/airflow/dbt/scripts
        - ./dbt/profiles:/opt/airflow/dbt_profiles
        - ./project:/opt/airflow/dbt_project

**Volume'ы — критичны:**

| Монтирование                       | Что даёт                                          |
|------------------------------------|---------------------------------------------------|
| `./airflow/dags:/opt/airflow/dags` | DAG-файлы доступны из хоста                       |
| `./airflow/logs`                   | Логи задач сохраняются                             |
| `./airflow/plugins`                | Кастомные плагины и операторы                     |
| `./airflow/config`                 | Кастомный `airflow.cfg` (опционально)              |
| `./dbt/scripts:/opt/airflow/dbt/scripts` | Скрипты генерации и загрузки                |
| `./dbt/profiles:/opt/airflow/dbt_profiles` | `profiles.yml` для dbt                    |
| `./project:/opt/airflow/dbt_project` | dbt-модели                                       |

Без этих volume'ов задача `dbt_run` упадёт с `No such file or directory` —
именно это и было одной из первых ошибок.

Сервис `airflow-scheduler`:

    airflow-scheduler:
      image: dbt_sample-airflow:latest
      command: scheduler
      volumes: [те же]

Scheduler парсит DAG'и, следит за расписанием, ставит задачи в Redis.

Сервис `airflow-worker`:

    airflow-worker:
      image: dbt_sample-airflow:latest
      command: celery worker
      volumes: [те же]

Worker забирает задачи из Redis и выполняет их. Может быть несколько
(для горизонтального масштабирования) — но в учебном проекте один.

Сервис `airflow-triggerer`:

    airflow-triggerer:
      image: dbt_sample-airflow:latest
      command: triggerer

Нужен для **deferred operators** (async-задачи). В нашем DAG не используется,
но часто присутствует в стандартном развёртывании.

---

## Отладка

### Проверить, что DAG виден

    docker exec -it airflow_scheduler airflow dags list

Ожидаемо:

    dag_id                         | fileloc                                     | owners    |
    ===============================+=============================================+===========+
    dbt_supply_chain_pipeline      | /opt/airflow/dags/dbt_supply_chain_dag.py   | data-team |

### Проверить, что init завершился

    docker compose logs airflow-init --tail 20

Ищи:

    User "admin" created with role "Admin"

### Запустить DAG вручную

    docker exec -it airflow_scheduler airflow dags trigger dbt_supply_chain_pipeline

Или через UI: **DAGs → dbt_supply_chain_pipeline → Trigger DAG (▶)**.

### Посмотреть статус всех DAG'ов

    docker exec -it airflow_scheduler airflow dags list-runs -d dbt_supply_chain_pipeline

### Логи конкретной задачи

Через UI: **Graph View → клик на задачу → Logs**.

Или через CLI:

    docker exec -it airflow_scheduler airflow tasks logs dbt_supply_chain_pipeline <run_id> dbt_run <try_number>

### Войти в контейнер

    docker exec -it airflow_scheduler bash

Внутри:

    airflow version
    ls /opt/airflow/dags/
    dbt --version
    ls /opt/airflow/dbt_project/

### Проверить подключения (Connections)

Через UI: **Admin → Connections**. Или через CLI:

    docker exec -it airflow_scheduler airflow connections list

### Проверить переменные (Variables)

    docker exec -it airflow_scheduler airflow variables list

---

## Частые проблемы

| Симптом                                                       | Причина                                    | Решение                                                              |
|---------------------------------------------------------------|--------------------------------------------|-----------------------------------------------------------------------|
| `dbt: command not found`                                     | PATH не включает `.local/bin`              | `"PATH": "/home/airflow/.local/bin:..."` в ENV DAG                    |
| `No such file or directory: /opt/airflow/dbt/scripts/...`    | Volume'ы не смонтированы в worker          | Добавить volume'ы в docker-compose для webserver, scheduler, worker    |
| `PermissionError: '/dbt_project/logs/dbt.log'`                | logs только для чтения                     | `dbt --log-path /tmp/dbt_logs run --target-path /tmp/dbt_target`       |
| `FileNotFoundError: /dbt/project/models/staging`              | Путь `/dbt/project` не существует          | Использовать `DBT_PROJECT_DIR=/opt/airflow/dbt_project`               |
| `SECRET_KEY not set`                                          | Не задан `SUPERSET_SECRET_KEY` в `.env`    | Добавить `AIRFLOW_FERNET_KEY` в `.env`                                 |
| DAG не появляется в UI                                        | Ошибка парсинга                            | `docker exec airflow_scheduler airflow dags list-import-errors`        |
| `ModuleNotFoundError: No module named 'cryptography'`         | Запуск `python`-скрипта на хосте            | Использовать готовый Fernet-key или `docker run python:3.11`           |
| `ResolutionImpossible` при `pip install`                      | Конфликт версий                             | Зафиксировать `dbt-core 1.6.2` + `dbt-starrocks 1.6.2` + `mysql-connector 8.0.22` |
| `Exited (137)` на worker                                      | OOM                                        | Остановить другие контейнеры, уменьшить память worker'а               |
| DAG в статусе `queued`, но не выполняется                     | Worker не запущен или не подключен         | Проверить `docker compose ps airflow-worker`, `celery inspect ping`    |
| `Cannot connect to Redis`                                     | Redis не запущен                            | `docker compose up -d redis`                                           |

---

## Как это связано с другими модулями

    airflow/dags/dbt_supply_chain_dag.py
        |
        +-- задачи используют скрипты из dbt/scripts/
        |
        +-- dbt-run использует profiles из dbt/profiles/
        |
        +-- dbt-run использует модели из project/models/
        |
        +-- все задачи пишут/читают StarRocks и MinIO через dbt_network

**Поток данных в DAG:**

    1. generate_and_upload  (запускает dbt/scripts/generate_and_upload.py)
         ↓ создаёт CSV в MinIO + stg_*.sql в project/models/staging/

    2. load_to_starrocks    (запускает dbt/scripts/load_s3_to_starrocks.py)
         ↓ создаёт raw_* в StarRocks

    3. dbt_run               (запускает `dbt run` в /opt/airflow/dbt_project)
         ↓ создаёт stg_* views + mart_* tables в StarRocks

    4. dbt_test              (запускает `dbt test`)
         ↓ прогоняет 9 тестов (unique, not_null)

**Ключевая идея:** Airflow не содержит бизнес-логики — он только
**запускает** внешние скрипты. Сами скрипты и модели лежат в `dbt/` и
`project/`.

---

## Полезные команды

    # Перезапустить Airflow (применить изменения в коде DAG'ов)
    docker compose restart airflow-scheduler airflow-webserver

    # Пересобрать образ (при изменении Dockerfile)
    docker compose build --no-cache airflow-init airflow-webserver airflow-scheduler airflow-worker airflow-triggerer

    # Полный рестарт Airflow
    docker compose stop airflow-webserver airflow-scheduler airflow-worker airflow-triggerer
    docker compose up -d airflow-init
    Start-Sleep -Seconds 30
    docker compose up -d airflow-webserver airflow-scheduler airflow-worker airflow-triggerer

    # Запустить DAG
    docker exec -it airflow_scheduler airflow dags trigger dbt_supply_chain_pipeline

    # Посмотреть статус
    docker exec -it airflow_scheduler airflow dags list-runs -d dbt_supply_chain_pipeline

    # Пейуза DAG (не запускать по расписанию)
    docker exec -it airflow_scheduler airflow dags pause dbt_supply_chain_pipeline

    # Unpause DAG
    docker exec -it airflow_scheduler airflow dags unpause dbt_supply_chain_pipeline

    # Backfill прошлых дат
    docker exec -it airflow_scheduler airflow dags backfill dbt_supply_chain_pipeline -s 2026-10-01 -e 2026-10-10

    # Очистить задачу (для перезапуска)
    docker exec -it airflow_scheduler airflow tasks clear dbt_supply_chain_pipeline -t dbt_run

    # Проверить память
    docker stats --no-stream | Select-String "airflow"

---

## Ссылки

- Airflow Docs: https://airflow.apache.org/docs/
- BashOperator: https://airflow.apache.org/docs/apache-airflow/stable/howto/operator/bash.html
- CeleryExecutor: https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/executor/celery.html
- DAG best practices: https://airflow.apache.org/docs/apache-airflow/stable/best-practices.html
- astronomer-cosmos: https://astronomer.github.io/astronomer-cosmos/
- Проект в целом: см. ../README.md