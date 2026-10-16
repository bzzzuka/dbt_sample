# dbt — инфраструктура трансформаций

Модуль отвечает за сборку dbt-образа, подключение к StarRocks и выполнение
пайплайна «генерация данных → загрузка в S3 → загрузка в StarRocks → dbt run».

Здесь только **инфраструктура** — сам dbt-проект (модели, SQL) лежит в
соседней папке `../project/`.

---

## Структура

    dbt/
    ├── Dockerfile                       # Образ с dbt + драйвером StarRocks
    ├── README.md                        # Этот файл
    ├── profiles/
    │   └── profiles.yml                 # Подключение к StarRocks
    └── scripts/
        ├── init.sh                      # Entrypoint для data-init
        ├── run_dbt.sh                   # Entrypoint для dbt
        ├── generate_and_upload.py       # Генерация данных → S3
        └── load_s3_to_starrocks.py      # S3 → StarRocks

---

## Зачем это нужно

Модуль решает три задачи:

1. **Сборка окружения** — образ с dbt 1.6.2 + адаптером dbt-starrocks + драйвером.
2. **Генерация данных** — синтетические 15 таблиц × ~120 колонок в S3.
3. **Загрузка и трансформации** — данные попадают в StarRocks, затем dbt строит модели.

Один Dockerfile → один образ → два сервиса в docker-compose:

    data-init  (entrypoint: init.sh)        — генерация + загрузка
    dbt        (entrypoint: run_dbt.sh)     — dbt run + dbt test

Разные entrypoint, одинаковый образ.

---

## Dockerfile

**Базовый образ:** python:3.11-slim

**Что устанавливается:**

- venv в /opt/venv
- dbt-core==1.6.2
- dbt-starrocks==1.6.2
- mysql-connector-python==8.0.22
- boto3, pandas, requests (для генерации и загрузки)

**Почему именно такие версии:**

| Пакет                       | Версия   | Причина                                                |
|-----------------------------|----------|--------------------------------------------------------|
| dbt-core                    | 1.6.2    | Проверенная пара с dbt-starrocks 1.6.2                 |
| dbt-starrocks               | 1.6.2    | Совместим с dbt-core 1.6.2 (более новые требуют 1.7+)  |
| mysql-connector-python      | 8.0.22   | Единственная версия без бага `server_version`          |
| protobuf                    | НЕ ставим| Подтягивается автоматически                            |

**Обходные пути в Dockerfile:**

1. **Не указываем версию protobuf** — dbt-core 1.6.2 сам подберёт совместимую.
   Версия 4.25.3 ломает dbt (несовместимость с C-расширением).

2. **mysql-connector-python устанавливается через --force-reinstall --no-deps** —
   иначе pip отвергнет версию 8.0.22 из-за конфликта с требованием dbt-starrocks
   (>=8.1). Мы знаем, что работает, — форсируем установку.

3. **Зеркало PyPI** — Tsinghua (pypi.tuna.tsinghua.edu.cn) для скорости из РФ.

**Переменные окружения:**

    PATH=/opt/venv/bin:$PATH
    DBT_PROFILES_DIR=/dbt/profiles

**Что копируется:**

- profiles/profiles.yml → /dbt/profiles/profiles.yml
- scripts/ → /dbt/scripts/

**Рабочая директория:** /dbt/project (монтируется с хоста).

---

## profiles/profiles.yml

**Назначение:** описание подключения dbt к StarRocks.

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

**Ключевые моменты:**

- `host: starrocks` — имя сервиса в docker-compose, резолвится внутри сети.
- Параметры читаются из env-переменных (см. .env в корне).
- `use_pure` НЕ указываем — не поддерживается схемой dbt-starrocks 1.6.2.

**Как dbt находит профиль:**

Переменная `DBT_PROFILES_DIR=/dbt/profiles` задана в Dockerfile.
Без неё dbt искал бы профиль в ~/.dbt/profiles.yml.

---

## scripts/init.sh

**Entrypoint сервиса `data-init`.**

**Что делает по шагам:**

1. Логирует начало работы.
2. Вызывает `python /dbt/scripts/generate_and_upload.py` — генерация данных.
3. Вызывает `python /dbt/scripts/load_s3_to_starrocks.py` — загрузка в StarRocks.
4. Логирует завершение.

**Особенности:**

- `set -euo pipefail` — остановка при первой ошибке.
- Не использует Python wrapper — bash проще для последовательных шагов.
- Контейнер после завершения получает статус `Exited 0`.

**Когда запускается:**

Автоматически при `docker compose up`, если у сервиса `data-init` ещё нет
успешного запуска. Или вручную:

    docker compose run --rm data-init

---

## scripts/run_dbt.sh

**Entrypoint сервиса `dbt`.**

**Что делает по шагам:**

1. `cd /dbt/project` — переход в папку dbt-проекта.
2. `dbt debug` — проверка подключения к StarRocks.
3. `dbt run` — сборка всех моделей (15 stg + 6 mart).
4. `dbt test` — прогон тестов (9 штук).

**Когда запускается:**

Автоматически после успешного завершения `data-init`. Или вручную:

    docker compose run --rm dbt dbt run

**Альтернативные команды:**

    # Только одна модель
    docker compose run --rm --no-deps dbt dbt run --select stg_suppliers

    # Только тесты
    docker compose run --rm --no-deps dbt dbt test

    # Список моделей
    docker compose run --rm --no-deps dbt dbt ls

Флаг `--no-deps` пропускает повторный запуск data-init — быстрее.

---

## scripts/generate_and_upload.py

**Назначение:** генератор синтетических бизнес-данных.

**Что генерирует:**

15 таблиц о поставках:

    suppliers              suppliers ratings
    supply_contracts       quality_checks
    supply_orders          returns
    supply_items           inventory_movements
    shipments              transport_routes
    warehouses             customs_declarations
    deliveries             supplier_ratings
    invoices
    payments

Каждая таблица — ~120 колонок + primary key + foreign keys.

**Логика работы:**

1. Определяет схему таблиц (core-колонки + FK + случайные из пула ~190 колонок).
2. Для каждой таблицы:
   - Опционально очищает старый префикс в S3.
   - Генерирует N строк с детерминированным seed.
   - Разбивает на чанки по CHUNK_SIZE.
   - Загружает в S3 через boto3.
3. Сохраняет `_schema.json` (типы колонок) — его использует загрузчик.
4. Генерирует dbt-модели `stg_*.sql` и `sources.yml` в `../project/models/staging/`.

**Параметры через env:**

| Переменная           | По умолчанию | Что делает                            |
|----------------------|--------------|---------------------------------------|
| ROWS                 | 5000         | Строк на таблицу                      |
| CHUNK_SIZE           | 2500         | Строк в одном CSV                     |
| RANDOM_SEED          | 42           | Seed для детерминированности          |
| COLUMNS_PER_TABLE    | 120          | Колонок на таблицу                    |
| CLEAN_BEFORE_UPLOAD  | false        | Удалять старые файлы перед загрузкой  |
| BATCH_OFFSET         | 0            | Смещение primary key (для инкремента) |
| LAYER                | stg          | Префикс слоя в S3                     |
| PARTITION_DATE       | сегодня      | Дата-партиция                         |

**Структура в S3:**

    s3://dbt-bucket/stg/{table}/{YYYY-MM-DD}/{table}_part_NNN.csv

Например:

    s3://dbt-bucket/stg/suppliers/2026-10-16/suppliers_part_001.csv
    s3://dbt-bucket/stg/suppliers/2026-10-16/suppliers_part_002.csv

**Типы колонок:**

Пул колонок содержит ~190 типов:

- code — текстовые коды (SKU, INVOICE, AWB)
- date / datetime — даты
- money — NUMERIC(15,2)
- int — INTEGER
- float — NUMERIC(15,3)
- name / product / category — строки из справочников
- country / city / region — гео
- enum — из фиксированных списков (incoterms, transport_mode, ...)
- bool — флаги
- coord — координаты
- email / phone / url — контакты

**Связность данных:**

FK-колонки ссылаются на реальные PK других таблиц:

    orders.customer_id  →  suppliers.supplier_id
    supply_items.order_id → supply_orders.order_id
    ...

Это позволяет строить осмысленные JOIN'ы в mart-моделях.

**Опциональное сохранение локально:**

    WRITE_LOCAL=true
    LOCAL_DIR=./data

Сохранит CSV в ./data/ на хосте (для отладки).

---

## scripts/load_s3_to_starrocks.py

**Назначение:** загрузка CSV из MinIO в StarRocks.

**Логика работы:**

1. Читает `/dbt/_schema.json` — типы колонок.
2. Ждёт, пока StarRocks будет готов (`SHOW BACKENDS` вернёт alive BE).
3. Для каждой таблицы:
   - `DROP TABLE IF EXISTS raw_{table}`
   - `CREATE TABLE raw_{table} (...) ENGINE=OLAP DUPLICATE KEY ...`
   - Читает каждый CSV через `INSERT INTO ... SELECT * FROM FILES(...)`
4. Проверяет `COUNT(*)`.

**Ключевые решения:**

1. **Загрузка по одному файлу** (не wildcards).
   StarRocks 3.4.10 не резолвит `*.csv` для MinIO. Обходим циклом:
   получаем список файлов через `boto3.list_objects_v2`, грузим по одному.

2. **FILES() вместо внешнего ETL.**
   StarRocks сам читает S3 — не нужно тащить данные через Python.

3. **Path-style URL.**
   `aws.s3.enable_path_style_access=true` — единственный способ для MinIO.

4. **SSL отключён.**
   `aws.s3.enable_ssl=false` — MinIO работает по HTTP.

5. **`replication_num=1`** — обязательно для однонодового кластера.

**SQL-паттерн:**

    INSERT INTO raw_suppliers
    SELECT * FROM FILES(
        "path" = "s3://dbt-bucket/stg/suppliers/2026-10-16/suppliers_part_001.csv",
        "format" = "csv",
        "csv.skip_header" = "1",
        "aws.s3.endpoint" = "http://minio:9000",
        "aws.s3.access_key" = "minioadmin",
        "aws.s3.secret_key" = "minioadmin",
        "aws.s3.enable_ssl" = "false",
        "aws.s3.enable_path_style_access" = "true"
    );

**Параметры через env:**

| Переменная          | По умолчанию        | Что делает              |
|---------------------|---------------------|-------------------------|
| STARROCKS_HOST      | starrocks           | Хост StarRocks FE       |
| STARROCKS_PORT      | 9030                | Порт MySQL-протокола    |
| STARROCKS_USER      | root                | Пользователь            |
| STARROCKS_SCHEMA    | analytics           | База данных             |
| MINIO_ENDPOINT      | http://minio:9000   | Endpoint MinIO          |
| MINIO_BUCKET        | dbt-bucket          | Бакет                   |
| SCHEMA_JSON_PATH    | /dbt/_schema.json   | Путь к схеме            |

---

## Как это связано с docker-compose

Сервис `data-init`:

    data-init:
      build: { context: ./dbt, dockerfile: Dockerfile }
      depends_on:
        starrocks: { condition: service_started }
        minio: { condition: service_healthy }
      volumes:
        - ./project:/dbt/project          # монтирование dbt-проекта
      entrypoint: ["/dbt/scripts/init.sh"]

Сервис `dbt`:

    dbt:
      build: { context: ./dbt, dockerfile: Dockerfile }
      depends_on:
        data-init: { condition: service_completed_successfully }
      volumes:
        - ./project:/dbt/project
      working_dir: /dbt/project
      entrypoint: ["/dbt/scripts/run_dbt.sh"]

**Ключевые моменты:**

- Оба сервиса используют один образ → одна сборка.
- Оба монтируют `./project` → dbt видит модели, скрипты могут их генерировать.
- `data-init` ждёт healthy MinIO.
- `dbt` ждёт успешного завершения `data-init`.

---

## Отладка

### Проверить, что dbt видит модели

    docker compose run --rm --no-deps dbt dbt ls

Должно вывести 21 модель:

    my_dbt_project.mart_delivery_kpi
    my_dbt_project.mart_payment_summary
    ...
    my_dbt_project.stg_suppliers
    ...

### Проверить подключение к StarRocks

    docker compose run --rm --no-deps dbt dbt debug

Ждём: `Connection test: [OK connection ok]`.

### Посмотреть сгенерированный SQL

    docker compose run --rm --no-deps dbt dbt compile

Скомпилированные модели попадут в `/dbt/project/target/compiled/`.

### Логи контейнера

    docker compose logs dbt --tail 50
    docker compose logs data-init --tail 50

### Войти в контейнер

    docker compose run --rm --entrypoint bash dbt

Внутри:

    dbt --version
    ls /dbt/project/
    ls /dbt/project/models/staging/

Выйти: exit.

---

## Частые проблемы

| Симптом                                                     | Причина                              | Решение                                                     |
|-------------------------------------------------------------|--------------------------------------|-------------------------------------------------------------|
| `dbt: command not found`                                    | PATH не включает /opt/venv/bin       | В Dockerfile: ENV PATH="/opt/venv/bin:$PATH"                 |
| `CMySQLConnection object has no setter`                     | Несовместимость драйвера             | mysql-connector-python==8.0.22 + --force-reinstall --no-deps|
| `profiles.yml file [ERROR invalid]`                         | Ошибка в YAML / лишний параметр      | Убрать use_pure, проверить отступы                          |
| `ResolutionImpossible`                                      | Конфликт версий при pip install      | Ставить драйвер с --force-reinstall --no-deps               |
| `Permission denied: '/dbt/project/logs/dbt.log'`            | logs только для чтения в Airflow     | `dbt --log-path /tmp/dbt_logs run --target-path /tmp/dbt_target` |

---

## Ссылки

- dbt Documentation: https://docs.getdbt.com/
- dbt-starrocks GitHub: https://github.com/StarRocks/dbt-starrocks
- StarRocks SQL reference: https://docs.starrocks.io/docs/sql-reference/
- Проект в целом: см. ../README.md