# Модуль 02 — Airflow (оркестрация)

**Файлы модуля:**

- `airflow/Dockerfile`
- `airflow/dags/dbt_supply_chain_dag.py`
- `airflow/README.md` (частично устарел)
- сервисы `airflow-*` в `docker-compose.yml`
- переменные `AIRFLOW_*` в `.env`

---

## 1. Зачем нужен Airflow

Airflow запускает пайплайн по расписанию и хранит историю запусков.
Он **не содержит бизнес-логику**: задачи вызывают внешние Python-скрипты и
`dbt`-команды.

Пайплайн:

```
generate_and_upload
  -> load_to_starrocks
  -> generate_retail
  -> load_retail_to_starrocks
  -> dbt_run
  -> dbt_test
```

---

## 2. Компоненты

| Сервис | Роль |
|---|---|
| `postgres-airflow` | Метаданные Airflow: DAG runs, task instances, connections, variables |
| `redis` | Celery broker (очередь задач) |
| `airflow-init` | One-shot: миграции БД + создание admin |
| `airflow-webserver` | Web UI на 8080 |
| `airflow-scheduler` | Парсит DAG-и и ставит задачи в очередь |
| `airflow-worker` | Выполняет задачи Celery |
| `airflow-triggerer` | Deferred operators (в текущем DAG не используется) |

Все Airflow-сервисы используют один образ `dbt_sample-airflow:latest`,
который собирается в `airflow-init`.

---

## 3. Образ Airflow

Файл: `airflow/Dockerfile`.

База:

```dockerfile
FROM apache/airflow:2.10.5-python3.11
```

Почему Python 3.11: `dbt-core==1.6.2` не собирается на Python 3.12.

Устанавливается:

| Пакет | Зачем |
|---|---|
| `apache-airflow==2.10.5` | фиксируем версию |
| `dbt-core==1.6.2` | запуск `dbt run/test` внутри worker |
| `dbt-starrocks==1.6.2` | адаптер StarRocks |
| `boto3`, `botocore` | работа с MinIO/S3 |
| `pymysql` | подключение Python-скриптов к StarRocks |
| `pandas`, `requests` | вспомогательные библиотеки |
| `mysql-connector-python==8.0.33` | принудительный откат для совместимости с dbt-starrocks |

> В README модуля упоминается `astronomer-cosmos` и `requirements.txt`.
> В текущем Dockerfile их нет. Актуальный состав — то, что выше.

---

## 4. DAG

Файл: `airflow/dags/dbt_supply_chain_dag.py`.

### 4.1. Параметры DAG

```python
dag_id="dbt_supply_chain_pipeline"
schedule="0 3 * * *"      # каждый день в 03:00 UTC
catchup=False
max_active_runs=1
tags=["dbt", "starrocks", "retail"]
```

`start_date=datetime(2026, 1, 1)`.

Новые DAG создаются на паузе, потому что в compose задано:

```yaml
AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION=True
```

После первого запуска DAG нужно снять с паузы:

```powershell
docker exec airflow_scheduler airflow dags unpause dbt_supply_chain_pipeline
```

### 4.2. Переменные ENV

DAG передаёт переменные в каждую задачу через `env=ENV`:

| Переменная | Значение | Зачем |
|---|---|---|
| `PATH` | `/home/airflow/.local/bin:...` | чтобы найти `dbt` |
| `STARROCKS_HOST` | `starrocks` | DNS внутри сети |
| `STARROCKS_PORT` | `9030` | MySQL-протокол |
| `STARROCKS_USER` | `root` | пользователь |
| `STARROCKS_PASSWORD` | пусто | локальный пароль |
| `STARROCKS_SCHEMA` | `analytics` | схема |
| `STARROCKS_CATALOG` | `default_catalog` | каталог StarRocks |
| `MINIO_ENDPOINT` | `http://minio:9000` | S3 endpoint |
| `MINIO_ROOT_USER` | `minioadmin` | доступ |
| `MINIO_ROOT_PASSWORD` | `minioadmin` | доступ |
| `MINIO_BUCKET` | `dbt-bucket` | bucket |
| `MINIO_REGION` | `us-east-1` | регион |
| `LAYER` | `stg` | префикс supply chain |
| `ROWS` | `5000` | строк на таблицу |
| `CHUNK_SIZE` | `2500` | строк в CSV-файле |
| `COLUMNS_PER_TABLE` | `120` | колонок в supply chain |
| `WRITE_LOCAL` | `false` | не писать локальные CSV |
| `SCHEMA_JSON_PATH` | `/tmp/_schema.json` | схема supply chain |
| `RETAIL_PREFIX` | `retail/stg` | префикс retail |
| `RETAIL_SCHEMA_JSON_PATH` | `/tmp/_retail_schema.json` | схема retail |
| `DBT_PROJECT_DIR` | `/opt/airflow/dbt_project` | dbt-проект |
| `DBT_PROFILES_DIR` | `/opt/airflow/dbt_profiles` | profiles |

> Это важное ограничение: значения захардкожены в DAG. Если меняете
> `.env`, синхронизируйте DAG `ENV` вручную. В будущем лучше вынести их в
> Airflow Variables/Connections.

### 4.3. Задачи

| Task ID | Команда | Что делает |
|---|---|---|
| `generate_and_upload` | `python /opt/airflow/dbt/scripts/generate_and_upload.py` | 15 CSV supply chain → MinIO, схема, dbt staging |
| `load_to_starrocks` | `python /opt/airflow/dbt/scripts/load_s3_to_starrocks.py` | MinIO → `analytics.raw_*` |
| `generate_retail` | `python /opt/airflow/dbt/scripts/generate_retail.py` | 11 CSV retail → MinIO |
| `load_retail_to_starrocks` | `python /opt/airflow/dbt/scripts/load_retail_to_starrocks.py` | MinIO → `analytics.raw_retail_*` |
| `dbt_run` | `dbt run --profiles-dir /opt/airflow/dbt_profiles --target-path /tmp/dbt_target` | создаёт `stg_*` views и `mart_*` tables |
| `dbt_test` | `dbt test ...` | 19 тестов |

Почему `/tmp` для логов и target:

- `/opt/airflow/dbt_project` смонтирован из хоста и может быть read-only
  для процесса;
- `/tmp/dbt_logs` и `/tmp/dbt_target` всегда доступны на запись.

### 4.4. Зависимости

```python
gen >> load >> retail_gen >> retail_load >> run >> test
```

Задачи выполняются строго последовательно.

---

## 5. Авторизация

### 5.1. Учётные данные

`airflow-init` создаёт admin из `.env`:

```env
AIRFLOW_ADMIN_USERNAME=admin
AIRFLOW_ADMIN_PASSWORD=admin
```

В `docker-compose.yml`:

```yaml
- _AIRFLOW_WWW_USER_USERNAME=${AIRFLOW_ADMIN_USERNAME}
- _AIRFLOW_WWW_USER_PASSWORD=${AIRFLOW_ADMIN_PASSWORD}
```

### 5.2. Ключи

| Переменная | Назначение |
|---|---|
| `AIRFLOW__WEBSERVER__SECRET_KEY` | подпись сессий и CSRF-токенов; должна быть одинаковой у всех Airflow-сервисов |
| `AIRFLOW_FERNET_KEY` | шифрование connections; валидный 44-символьный base64 |

Если `SECRET_KEY` не передан в контейнер, Airflow генерирует свой. При
пересоздании контейнера ключ меняется, и старые сессии/CSRF-токены
инвалидируются. В проекте ключ передаётся явно.

### 5.3. Если `admin/admin` не работает

Типичная ошибка:

```
ValueError: unsupported hash type scrypt:32768:8:1
```

Причина: старый пароль был сохранён Werkzeug 3.x в формате `scrypt`, а
Airflow 2.10.5 использует Werkzeug 2.2.3 и не умеет его проверять.

Исправление:

```powershell
docker exec airflow_webserver airflow users reset-password `
  --username admin --password admin
```

После сброса хеш становится `pbkdf2:sha256:...`, вход работает.

Не отключайте CSRF (`WTF_CSRF_ENABLED=False`) как «фикс» — это маскирует
проблему.

---

## 6. Volumes, которые видит Airflow

В `docker-compose.yml` для webserver/scheduler/worker/triggerer смонтированы:

| Host | Container | Зачем |
|---|---|---|
| `./airflow/dags` | `/opt/airflow/dags` | DAG-файлы |
| `./airflow/logs` | `/opt/airflow/logs` | логи задач |
| `./airflow/plugins` | `/opt/airflow/plugins` | плагины |
| `./airflow/config` | `/opt/airflow/config` | кастомный config (если есть) |
| `./dbt/scripts` | `/opt/airflow/dbt/scripts` | Python-скрипты |
| `./dbt/profiles` | `/opt/airflow/dbt_profiles` | `profiles.yml` |
| `./project` | `/opt/airflow/dbt_project` | dbt-модели |

Если volume не смонтирован, задача упадёт с `No such file or directory`.

---

## 7. Как проверять

### 7.1. DAG виден

```powershell
docker exec airflow_scheduler airflow dags list
docker exec airflow_scheduler airflow dags list-import-errors
```

Ожидаемо: `dbt_supply_chain_pipeline`, ошибок импорта нет.

### 7.2. Запуск

```powershell
docker exec airflow_scheduler airflow dags unpause dbt_supply_chain_pipeline
docker exec airflow_scheduler airflow dags trigger dbt_supply_chain_pipeline
docker exec airflow_scheduler airflow dags list-runs -d dbt_supply_chain_pipeline
```

### 7.3. Статусы задач

```powershell
docker exec airflow_scheduler airflow tasks states-for-dag-run `
  dbt_supply_chain_pipeline <run_id>
```

Все 6 задач должны быть `success`.

### 7.4. Логи

```powershell
docker compose logs --tail=200 airflow-scheduler
docker compose logs --tail=200 airflow-worker
docker compose logs --tail=200 airflow-webserver
```

Логи конкретной задачи также доступны в UI:
DAG → Graph → Task → Logs.

### 7.5. Проверить пользователей и БД

```powershell
docker exec airflow_webserver airflow users list
docker exec airflow_webserver airflow db check
```

---

## 8. Как изменить DAG

1. Отредактируйте `airflow/dags/dbt_supply_chain_dag.py`.
2. Перезапустите scheduler/webserver/worker:

```powershell
docker compose restart airflow-scheduler airflow-webserver airflow-worker
```

3. Проверьте import errors:

```powershell
docker exec airflow_scheduler airflow dags list-import-errors
```

4. Запустите DAG вручную.

Подробные рецепты — в [`../DEVELOPMENT_GUIDE.md`](../DEVELOPMENT_GUIDE.md).

---

## 9. Ограничения и предупреждения

1. **`spark_etl_dag.py` отсутствует.** Он упоминается в старом README, но
   не реализован: Airflow-контейнер не имеет Docker socket и Spark runtime.
   Spark ETL запускается вручную.
2. **`start-airflow.ps1` не запускает `airflow-worker`.** После него
   выполните `docker compose up -d airflow-worker` или используйте
   `docker compose up -d`.
3. **Credentials в DAG `ENV` захардкожены.** Синхронизируйте с `.env`.
4. **`astronomer-cosmos` не установлен.** Он не используется.
5. **`airflow/README.md` устарел** (описывает 4 задачи и `requirements.txt`).
   Актуальная документация — этот файл и `docs/`.

---

## 10. Частые ошибки

| Ошибка | Причина | Решение |
|---|---|---|
| `dbt: command not found` | PATH | проверить `ENV["PATH"]` |
| `No such file: /opt/airflow/dbt/scripts/...` | volume не смонтирован | проверить volumes |
| DAG не появился | import error | `airflow dags list-import-errors` |
| DAG `queued`, не выполняется | worker не запущен | `docker compose up -d airflow-worker` |
| `scrypt` при логине | старый хеш | `airflow users reset-password` |
| `SECRET_KEY` mismatch | разные значения | один и тот же ключ во всех сервисах |
| `PermissionError` при dbt | запись в read-only | `/tmp/dbt_logs`, `/tmp/dbt_target` |
| OOM (`Exited 137`) | мало RAM | увеличить память / режимы |

---

## 11. Связанные документы

- [`03-dbt.md`](03-dbt.md)
- [`04-data-generation.md`](04-data-generation.md)
- [`../RUNBOOK.md`](../RUNBOOK.md)
- [`../ARCHITECTURE.md`](../ARCHITECTURE.md)
