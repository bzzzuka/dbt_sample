# Модуль 01 — инфраструктура Docker Compose

**Файлы модуля:**

- `docker-compose.yml`
- `.env`
- `.gitignore`
- `start-all.ps1`, `start-airflow.ps1`, `start-superset.ps1`

---

## 1. Что делает модуль

Инфраструктурный слой описывает:

- какие контейнеры запускаются;
- какие у них образы, порты и volumes;
- кто от кого зависит;
- какие healthcheck используются;
- какие переменные окружения передаются в контейнеры.

Бизнес-логики здесь нет. Compose только собирает и связывает сервисы.

---

## 2. Карта сервисов

### 2.1. Долгоживущие сервисы

| Сервис | Образ | Роль |
|---|---|---|
| `starrocks` | `starrocks/allin1-ubuntu:3.4-latest` | OLAP DWH (FE+BE в одном) |
| `minio` | `ghcr.io/coollabsio/minio:latest` | S3-хранилище |
| `superset` | `./superset/Dockerfile` | Superset webserver |
| `superset-worker` | `./superset/Dockerfile` | Celery worker Superset |
| `postgres-airflow` | `postgres:15-alpine` | Метаданные Airflow |
| `redis` | `redis:7-alpine` | Celery broker + Superset results |
| `airflow-webserver` | `dbt_sample-airflow:latest` | Airflow UI |
| `airflow-scheduler` | `dbt_sample-airflow:latest` | Планировщик |
| `airflow-worker` | `dbt_sample-airflow:latest` | Celery worker Airflow |
| `airflow-triggerer` | `dbt_sample-airflow:latest` | Triggerer |
| `iceberg-rest` | `apache/iceberg-rest-fixture:1.10.1` | Iceberg REST catalog |
| `spark-iceberg` | `apache/spark:3.5.6` | Контейнер для Spark ETL |

### 2.2. One-shot сервисы

| Сервис | Что делает | Ожидаемый статус |
|---|---|---|
| `airflow-init` | миграции БД + создание admin | `Exited (0)` |
| `data-init` | генерация supply chain + retail, загрузка в S3/StarRocks | `Exited (0)` |
| `dbt` | `dbt debug/run/test` | `Exited (0)` |
| `superset-init` | миграции Superset + admin + StarRocks connection | `Exited (0)` |
| `superset-dashboards` | создание датасетов, чартов, дашбордов | `Exited (0)` |

> `Exited (0)` — успех. `Exited (1+)` — ошибка. Смотрите
> `docker compose logs <service>`.

---

## 3. Порты

| Порт хоста | Сервис | Зачем |
|---|---|---|
| 8080 | `airflow-webserver` | Airflow UI |
| 8088 | `superset` | Superset UI |
| 9000 | `minio` | S3 API |
| 9001 | `minio` | MinIO Console |
| 8030 | `starrocks` | StarRocks FE UI |
| 9030 | `starrocks` | StarRocks MySQL protocol |
| 8040 | `starrocks` | StarRocks BE |
| 8181 | `iceberg-rest` | Iceberg REST API |
| 4040 | `spark-iceberg` | Spark UI (во время job) |
| 8082 | `spark-iceberg` | Проброшен, но Spark Master не запущен |
| 8888 | `spark-iceberg` | Проброшен, Jupyter не запущен |
| 10000 | `spark-iceberg` | Проброшен, Thrift Server не запущен |

Проверить занятость порта:

```powershell
Get-NetTCPConnection -LocalPort 8080 -State Listen
```

Если 8080 занят — Airflow не стартует. Частая причина — старый контейнер
(например, Trino/Hive из предыдущей версии проекта). Удалите его:

```powershell
docker ps -a
docker rm -f <container>
```

---

## 4. Сети

Все сервисы подключены к bridge-сети `dbt_network`.

Внутри сети используются DNS-имена сервисов:

- `starrocks:9030`
- `minio:9000`
- `iceberg-rest:8181`
- `postgres-airflow:5432`
- `redis:6379`

Поэтому в конфигурациях пишут `host=starrocks`, а не `host=localhost`.
`localhost` внутри контейнера — это сам контейнер, а не хост.

---

## 5. Volumes

| Volume | Сервис | Что хранит |
|---|---|---|
| `starrocks_data` | `starrocks` | Данные и метаданные StarRocks |
| `minio_data` | `minio` | CSV, Iceberg warehouse |
| `superset_home` | Superset-сервисы | SQLite metadata Superset |
| `postgres_airflow_data` | `postgres-airflow` | Метаданные Airflow |

`docker compose down` **не удаляет** volumes.  
`docker compose down -v` **удаляет** их. Используйте `-v` только для полного
сброса.

---

## 6. Зависимости и порядок запуска

Упрощённо:

```
starrocks ─┬─> data-init ─> dbt
minio ─────┘
redis ─┬─> superset ─> superset-dashboards
       ├─> superset-worker
       └─> airflow-init ─> airflow-webserver/scheduler/worker/triggerer
postgres-airflow ─> airflow-init
iceberg-rest ─┐
minio ────────┴─> spark-iceberg
```

Важные условия:

- `data-init` ждёт `starrocks` и `minio`;
- `dbt` ждёт успешного завершения `data-init`;
- `superset` ждёт `superset-init` и healthy `redis`;
- `superset-dashboards` ждёт healthy `superset` и `redis`;
- `airflow-init` ждёт Postgres/Redis;
- Airflow-сервисы ждут `airflow-init`;
- Spark-контейнер зависит от `iceberg-rest` и `minio`.

---

## 7. Healthcheck

| Сервис | Проверка |
|---|---|
| `minio` | `mc ready local` |
| `postgres-airflow` | `pg_isready` |
| `redis` | `redis-cli ping` |
| `airflow-webserver` | `curl /health` |
| `airflow-worker` | `celery -A airflow.executors.celery_executor.app inspect ping` |
| `superset` | HTTP `/health` |
| `superset-worker` | `celery -A superset.tasks.celery_app:app inspect ping` |
| `iceberg-rest` | HTTP `/v1/config` |

Без healthcheck:

- `starrocks` — известное ограничение allin1-образа;
- `spark-iceberg` — контейнер-держатель;
- `airflow-scheduler`, `airflow-triggerer` — в текущем compose без healthcheck;
- one-shot сервисы.

Для сервисов без healthcheck статус `Up` — нормальный. Не считайте это ошибкой.

---

## 8. `.env`: как он работает

`.env` нужен Compose для подстановки `${VAR}` в `docker-compose.yml`.

Пример:

```yaml
environment:
  - STARROCKS_HOST=${STARROCKS_HOST}
```

означает: взять значение из `.env` и передать в контейнер.

Важно:

- `.env` **не** пробрасывает все переменные автоматически;
- если переменной нет в `environment` сервиса, контейнер её не увидит;
- изменения `.env` не применяются к уже запущенному контейнеру — нужен
  `docker compose up -d --force-recreate <service>`;
- проверить итоговую конфигурацию:

```powershell
docker compose config
```

### Основные переменные

| Переменная | Назначение |
|---|---|
| `STARROCKS_HOST/PORT/USER/PASSWORD/SCHEMA/CATALOG` | Подключение к StarRocks |
| `MINIO_ROOT_USER/PASSWORD` | Доступ к MinIO |
| `MINIO_ENDPOINT/BUCKET/REGION` | S3 endpoint, bucket, регион |
| `LAYER` | Префикс supply chain (`stg`) |
| `ROWS`, `CHUNK_SIZE`, `COLUMNS_PER_TABLE` | Параметры генерации supply chain |
| `AIRFLOW_ADMIN_USERNAME/PASSWORD` | admin для `airflow-init` |
| `AIRFLOW_FERNET_KEY` | Шифрование connections Airflow |
| `AIRFLOW__WEBSERVER__SECRET_KEY` | Подпись сессий/CSRF Airflow |
| `SUPERSET_SECRET_KEY` | Секрет Superset |

---

## 9. `.gitignore`

В репозиторий не должны попадать:

- `airflow/logs/`, `project/logs/`, `*.log`;
- `project/target/`, `target/`, `dbt_packages/`;
- `__pycache__/`, `*.pyc`;
- `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`;
- `.venv/`, `venv/`, `node_modules/`;
- `dbt/profiles/.user.yml`;
- `.env.local`, `.idea/`, `.vscode/`, `.DS_Store`, `Thumbs.db`;
- `.ivy2/`.

Если артефакт уже был закоммичен, одного `.gitignore` недостаточно — нужно
убрать его из индекса:

```powershell
git rm -r --cached airflow/logs project/logs project/target
git commit -m "chore: stop tracking runtime artifacts"
```

---

## 10. Start-скрипты

| Скрипт | Что запускает | Ограничение |
|---|---|---|
| `start-all.ps1` | StarRocks, MinIO, Redis, data-init, dbt, Superset, dashboards, Airflow (включая worker) | Фиксированные `Start-Sleep` |
| `start-airflow.ps1` | Airflow без Superset | **Не запускает `airflow-worker`** — добавьте `docker compose up -d airflow-worker` |
| `start-superset.ps1` | Superset без Airflow | Не запускает `superset-worker`; для дашбордов не критично |

Рекомендуемый путь — `docker compose up -d` (см. `RUNBOOK.md`). Скрипты —
удобные обёртки для слабых машин.

---

## 11. Частые проблемы

| Проблема | Причина | Решение |
|---|---|---|
| `port is already allocated` | порт занят | найти и остановить процесс/контейнер |
| `.env` изменили, но эффекта нет | контейнер не пересоздан | `docker compose up -d --force-recreate <service>` |
| `service_started` вместо healthy у StarRocks | нет healthcheck | это нормально |
| One-shot `Exited (1)` | ошибка шага | `docker compose logs <service>` |
| Airflow не видит `SECRET_KEY` | переменная не в `environment` | добавить в compose и пересоздать |
| Superset не строит графики | Redis results backend недоступен | проверить `redis` и `superset_config.py` |
| Не хватает памяти | несколько тяжёлых сервисов | режимы запуска / увеличить RAM |

---

## 12. Связанные документы

- [`../ARCHITECTURE.md`](../ARCHITECTURE.md)
- [`02-airflow.md`](02-airflow.md)
- [`03-dbt.md`](03-dbt.md)
- [`08-superset.md`](08-superset.md)
- [`../RUNBOOK.md`](../RUNBOOK.md)
