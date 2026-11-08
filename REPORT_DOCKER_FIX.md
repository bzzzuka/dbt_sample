# REPORT_DOCKER_FIX.md — исправление и проверка проекта dbt_sample

**Дата:** 2026-11-08  
**Исполнитель:** DevOps-инженер (Kilo Code)  
**Итоговый статус:** **READY WITH LIMITATIONS**

---

## 1. Краткое резюме

Проект приведён в рабочее состояние:

- удалены все остатки Trino/Hive из Docker (контейнеры, образы) и из кода/документации;
- устранён конфликт порта 8080 (его занимал старый контейнер `trino`);
- исправлены CRLF в shell-скриптах, из-за которых падали `data-init` и `superset-init`;
- Airflow-образ зафиксирован на 2.10.5, в него добавлены `boto3`, `botocore`, `pymysql`;
- исправлена MOEX-регрессия: `stg_moex_prices.sql` больше не удаляется генератором,
  `raw_moex_prices` создаётся в StarRocks, `sources.yml` содержит этот источник;
- Superset worker переведён на Redis broker и получил корректный healthcheck;
- Airflow worker получил корректный healthcheck через Celery app;
- добавлен отсутствовавший `spark/jobs/verify_iceberg.py`;
- `docker compose up -d --build` запускает стек без ошибок;
- Airflow DAG `dbt_supply_chain_pipeline` виден, импортируется без ошибок и успешно
  проходит тестовые запуски (все 4 задачи `success`);
- Spark ETL пишет Iceberg-таблицу, StarRocks читает её через `iceberg_lakehouse`
  (`SELECT COUNT(*) = 5000`);
- MinIO, Superset, Iceberg REST, dbt, StarRocks, Airflow проверены.

---

## 2. Исходное состояние

На момент начала работ:

- `docker compose.yml` содержал только актуальные сервисы (Trino/Hive в нём уже не было),
  но в Docker daemon **работали старые контейнеры**:
  - `trino` (`trinodb/trino:481`) — занимал порт **8080**, блокируя Airflow;
  - `hive_metastore` (`apache/hive:4.0.0`);
  - `hive_postgres` (`postgres:15-alpine`).
- В коде было **одно** упоминание Hive: `spark/README.md:328`
  («REST-каталог (не Hive, не Glue)»).
- Shell-скрипты `dbt/scripts/init.sh`, `dbt/scripts/run_dbt.sh`,
  `superset/init/init-db.sh` имели CRLF, из-за чего контейнеры падали:
  - `env: ‘bash\r’: No such file or directory`;
  - `set: -: invalid option`;
  - `syntax error: unexpected end of file`.
- В Airflow-образе при сборке не был зафиксирован `apache-airflow`, из-за чего
  pip подтянул 2.11.2 вместо 2.10.5.
- В Airflow-образе не были явно установлены `boto3` и `pymysql`, нужные скриптам DAG.
- `generate_and_upload.py` удалял **все** `stg_*.sql`, включая `stg_moex_prices.sql`,
  после чего `mart_moex_daily_returns.sql` ломал `dbt run`.
- `spark/jobs/verify_iceberg.py` отсутствовал, хотя упоминался в README.
- `superset-worker` падал с `sqlite3.OperationalError: unable to open database file`
  и рестартовал.
- Healthcheck Airflow worker использовал Celery без указания приложения и пытался
  подключиться к RabbitMQ на localhost.
- Healthcheck Superset worker проверял HTTP-порт 8088, который worker не слушает.

---

## 3. Упоминания Trino/Hive: что найдено и что сделано

| Файл / объект | Строка / объект | Что сделано |
|---|---|---|
| `spark/README.md` | 328: `REST-каталог (не Hive, не Glue)` | Переформулировано без Hive: `REST-каталог (удалённый сервис метаданных)` |
| Контейнер `trino` | `trinodb/trino:481` | Остановлен и удалён |
| Контейнер `hive_metastore` | `apache/hive:4.0.0` | Остановлен и удалён |
| Контейнер `hive_postgres` | `postgres:15-alpine` | Остановлен и удалён |
| Образ `trinodb/trino:481` | Docker image | Удалён |
| Образы `apache/hive:4.0.0`, `apache/hive:3.1.3` | Docker images | Удалены |

После правок финальный поиск:

```powershell
Get-ChildItem -Recurse -File |
  Where-Object { $_.FullName -notmatch '\\\.git\\' -and $_.Name -notin @('AUDIT_REPORT.md','REPORT_DOCKER_FIX.md') } |
  Select-String -Pattern 'trino|hive' -CaseSensitive:$false
```

Результат: **пусто**. Упоминания остались только в `AUDIT_REPORT.md` и этом отчёте
как историческая фиксация аудита.

Проверка Docker:

```powershell
docker ps -a --format "{{.Names}} {{.Image}}" | Select-String -Pattern 'trino|hive'
docker images --format "{{.Repository}}:{{.Tag}}" | Select-String -Pattern 'trino|hive'
docker volume ls --format "{{.Name}}" | Select-String -Pattern 'trino|hive'
```

Результат: **пусто**.

---

## 4. Изменённые файлы и суть изменений

### 4.1 Функциональные исправления

| Файл | Изменение |
|---|---|
| `docker-compose.yml` | `superset-worker`: добавлены `CELERY_BROKER_URL=redis://redis:6379/2`, `CELERY_RESULT_BACKEND=redis://redis:6379/3`, зависимость `redis: service_healthy`, healthcheck через Celery ping. `airflow-worker`: healthcheck переведён на `celery -A airflow.executors.celery_executor.app inspect ping`. |
| `airflow/Dockerfile` | Зафиксирован `apache-airflow==2.10.5`; убраны неиспользуемые `apache-airflow-providers-common-sql` и `astronomer-cosmos`; добавлены `boto3`, `botocore`, `pymysql`. |
| `dbt/scripts/init.sh` | CRLF → LF. |
| `dbt/scripts/run_dbt.sh` | CRLF → LF. |
| `superset/init/init-db.sh` | CRLF → LF. |
| `dbt/profiles/profiles.yml` | Удалён `use_pure: "true"` (не поддерживается схемой dbt-starrocks 1.6.2). |
| `dbt/scripts/generate_and_upload.py` | Больше не удаляет все `stg_*.sql`; при наличии `stg_moex_prices.sql` добавляет `raw_moex_prices` в `sources.yml`. |
| `dbt/scripts/load_s3_to_starrocks.py` | Добавлено создание `raw_moex_prices` (`CREATE TABLE IF NOT EXISTS`) для воспроизводимости `dbt run`. |
| `spark/README.md` | Удалено упоминание Hive. |
| `spark/init-starrocks.sql` | `CREATE EXTERNAL CATALOG` → `CREATE EXTERNAL CATALOG IF NOT EXISTS` (идемпотентность). |
| `spark/jobs/verify_iceberg.py` | Создан: проверяет каталоги, namespaces, таблицы и данные Iceberg. |

### 4.2 Артефакты запуска (изменены автоматически)

- `project/models/staging/sources.yml` — перегенерирован `data-init`, добавлен
  `raw_moex_prices`.
- `project/models/staging/stg_*.sql` — перегенерированы `data-init` (15 моделей).
- `project/target/*`, `project/logs/dbt.log` — артефакты `dbt run/test`.
- `airflow/logs/*`, `airflow/dags/__pycache__/*` — логи и pyc после запуска DAG.

Эти файлы не редактировались вручную; они обновились в результате проверочных
запусков.

---

## 5. Команды и результаты

| Команда | Результат |
|---|---|
| `docker compose config --quiet` | OK, ошибок YAML нет |
| `docker compose down` | Все контейнеры остановлены и удалены, volumes сохранены |
| `docker compose up -d --build` | Сборка и запуск успешны; one-shot сервисы завершились с кодом 0 |
| `docker compose ps` | Критичные сервисы `healthy`; `starrocks` и `spark-iceberg` без healthcheck (по README) |
| `docker compose logs data-init` | `Exited (0)`, 15 таблиц в S3 и StarRocks, `raw_moex_prices готова` |
| `docker compose logs dbt` | `dbt debug` — OK; `dbt run` — `PASS=23`; `dbt test` — `PASS=9` |
| `docker compose logs superset-init` | `Exited (0)`, миграции, admin, подключение StarRocks созданы |
| `docker compose logs airflow-init` | `Exited (0)`, миграции БД, admin, версия 2.10.5 |
| `docker exec airflow_scheduler airflow dags list` | `dbt_supply_chain_pipeline` виден |
| `docker exec airflow_scheduler airflow dags list-import-errors` | `No data found` |
| `docker exec airflow_scheduler airflow dags unpause ...` | DAG снят с паузы |
| `docker exec airflow_scheduler airflow dags trigger ...` | Ручной запуск создан |
| `docker exec airflow_scheduler airflow dags list-runs ...` | 3 запуска со статусом `success` (scheduled + 2 manual) |
| `docker exec airflow_scheduler airflow tasks states-for-dag-run ...` | Все 4 задачи `success` |
| `docker exec spark_iceberg spark-submit etl_supply_chain.py` | Прочитано 5000 строк × 121 колонка, таблица создана |
| `docker exec spark_iceberg spark-submit verify_iceberg.py` | `lakehouse`, `spark_catalog`, namespace `supply_chain`, таблица `suppliers`, данные читаются |
| `Get-Content spark\init-starrocks.sql \| docker exec -i starrocks mysql ...` | Каталог `iceberg_lakehouse` создан |
| `docker exec starrocks mysql ... "SHOW CATALOGS"` | `iceberg_lakehouse` присутствует |
| `docker exec starrocks mysql ... "SELECT COUNT(*) FROM iceberg_lakehouse.supply_chain.suppliers"` | `5000` |
| `docker exec dbt_minio mc ls ...` | Bucket `dbt-bucket`, файлы `stg/suppliers/2026-11-08/*.csv` |
| `Invoke-WebRequest http://localhost:8080/health` | `200` |
| `Invoke-WebRequest http://localhost:8088/health` | `200` |
| `Invoke-WebRequest http://localhost:8181/v1/config` | `200` |
| `Invoke-WebRequest http://localhost:9000/minio/health/live` | `200` |

---

## 6. Найденные ошибки и как исправлены

| Ошибка | Причина | Исправление |
|---|---|---|
| `superset-init` exit 2: `set: -: invalid option`, `$'\r'` | CRLF в `superset/init/init-db.sh` | Перевод файла в LF |
| `data-init` exit 127: `env: ‘bash\r’` | CRLF в `dbt/scripts/init.sh`, `run_dbt.sh` | Перевод файлов в LF |
| Airflow 2.11.2 вместо 2.10.5 | Незафиксированный `apache-airflow-providers-common-sql` / лишние пакеты | Зафиксирован `apache-airflow==2.10.5`, убраны неиспользуемые пакеты |
| `ModuleNotFoundError: boto3/pymysql` (потенциально) | В Airflow-образе не были явно установлены | Добавлены `boto3`, `botocore`, `pymysql` |
| `sqlite3.OperationalError: unable to open database file` в Superset worker | Celery использовал SQLite broker в недоступном пути | Worker переведён на Redis (`CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`) |
| Airflow worker healthcheck падал с `ConnectionRefusedError` | Celery CLI без приложения и broker URL | Healthcheck переведён на `celery -A airflow.executors.celery_executor.app inspect ping` |
| Superset worker `unhealthy` | Healthcheck проверял `localhost:8088`, worker не является webserver | Healthcheck заменён на Celery ping |
| `dbt run` падал после `data-init` | Генератор удалял `stg_moex_prices.sql`, а mart-модель оставалась | Генератор больше не удаляет все `stg_*.sql`; добавлен `raw_moex_prices` |
| Порт 8080 занят | Старый контейнер `trino` | Контейнер и образ Trino удалены |
| `verify_iceberg.py` отсутствовал | Файл не был создан | Добавлен |

---

## 7. Результаты проверки сервисов

| Сервис | Статус | Проверка |
|---|---|---|
| MinIO | Up, healthy | Bucket `dbt-bucket` доступен, CSV `stg/suppliers/2026-11-08/*.csv` (2 файла ~3.2 MiB) |
| StarRocks | Up, без healthcheck (по README) | Порт 9030 отвечает; `analytics.raw_suppliers` = 5000 строк; внешний каталог `iceberg_lakehouse` виден |
| Iceberg REST | Up, healthy | HTTP 8181 `/v1/config` → 200 |
| Spark + Iceberg | Up, без healthcheck | `etl_supply_chain.py` создал `lakehouse.supply_chain.suppliers` (5000 строк); `verify_iceberg.py` видит каталог, namespace, таблицу и данные |
| dbt | one-shot, Exited (0) | `dbt debug` OK; `dbt run` PASS=23; `dbt test` PASS=9 |
| Superset | Up, healthy | Init exit 0; UI 8088 `/health` → 200; worker healthy (Celery ping) |
| Airflow webserver | Up, healthy | 8080 `/health` → 200 |
| Airflow scheduler | Up | Парсит DAG, запускает задачи |
| Airflow worker | Up, healthy | Celery ping OK |
| Airflow triggerer | Up | Запущен |
| PostgreSQL (Airflow) | Up, healthy | `pg_isready` |
| Redis | Up, healthy | `redis-cli ping` |

---

## 8. Airflow DAG

**DAG:** `dbt_supply_chain_pipeline`  
**Файл:** `/opt/airflow/dags/dbt_supply_chain_dag.py`  
**Задачи:** `generate_and_upload → load_to_starrocks → dbt_run → dbt_test`

Проверки:

```powershell
docker exec airflow_scheduler airflow dags list
docker exec airflow_scheduler airflow dags list-import-errors
docker exec airflow_scheduler airflow dags unpause dbt_supply_chain_pipeline
docker exec airflow_scheduler airflow dags trigger dbt_supply_chain_pipeline
docker exec airflow_scheduler airflow dags list-runs -d dbt_supply_chain_pipeline
```

Результаты:

| Run ID | Статус | Задачи |
|---|---|---|
| `scheduled__2026-11-07T03:00:00+00:00` | success | все 4 success |
| `manual__2026-11-08T12:30:00+00:00` | success | все 4 success |
| `manual__2026-11-08T12:38:56+00:00` (после финального restart) | success | все 4 success |

Import errors: **нет**.

---

## 9. Iceberg и StarRocks external catalog

### Spark ETL

```powershell
docker exec spark_iceberg /opt/spark/bin/spark-submit /opt/spark/jobs/etl_supply_chain.py
```

Результат:

- прочитано 5000 строк × 121 колонка из `s3a://dbt-bucket/stg/suppliers/*/*.csv`;
- создана таблица `lakehouse.supply_chain.suppliers`;
- `SELECT COUNT(*)` = 5000;
- таблица видна в `SHOW TABLES IN lakehouse.supply_chain`.

### verify_iceberg.py

```powershell
docker exec spark_iceberg /opt/spark/bin/spark-submit /opt/spark/jobs/verify_iceberg.py
```

Результат:

- каталоги: `lakehouse`, `spark_catalog`;
- namespace: `supply_chain`;
- таблица: `suppliers`;
- данные читаются.

### StarRocks external catalog

```powershell
Get-Content -Raw spark\init-starrocks.sql | docker exec -i starrocks mysql -h 127.0.0.1 -P 9030 -uroot
docker exec starrocks mysql -h 127.0.0.1 -P 9030 -uroot -e "SHOW CATALOGS"
docker exec starrocks mysql -h 127.0.0.1 -P 9030 -uroot -e "SHOW DATABASES FROM iceberg_lakehouse"
docker exec starrocks mysql -h 127.0.0.1 -P 9030 -uroot -e "SHOW TABLES FROM iceberg_lakehouse.supply_chain"
docker exec starrocks mysql -h 127.0.0.1 -P 9030 -uroot -e "SELECT COUNT(*) FROM iceberg_lakehouse.supply_chain.suppliers"
```

Результат:

- `iceberg_lakehouse` типа `Iceberg` присутствует;
- база `supply_chain` видна;
- таблица `suppliers` видна;
- `COUNT(*)` = **5000**.

---

## 10. dbt: фактическое количество моделей

`dbt run` / `dbt test`:

```
Found 23 models, 9 tests, 16 sources
Done. PASS=23 WARN=0 ERROR=0 SKIP=0 TOTAL=23
Done. PASS=9   WARN=0 ERROR=0 SKIP=0 TOTAL=9
```

Состав:

- 16 staging-моделей: 15 supply-chain + `stg_moex_prices`;
- 7 mart-моделей: 6 supply-chain + `mart_moex_daily_returns`;
- 9 тестов (как и заявлено в README).

README заявляет 15 stg + 6 mart. Фактически в репозитории присутствовала
дополнительная MOEX-функциональность. Она **сохранена** (не удалена), потому что
это пользовательский код и данные; генерация исправлена так, чтобы MOEX-модель
не ломала пайплайн. Если требуется строго 15+6, нужно отдельно удалить
`stg_moex_prices.sql`, `mart_moex_daily_returns.sql`, MOEX-скрипты и `MOEX_*`
из `.env` — это осознанно не сделано в рамках данной задачи.

---

## 11. Как самостоятельно проверить проект

```powershell
# 1. Полный перезапуск
docker compose down
docker compose up -d --build
docker compose ps

# 2. MinIO
docker exec dbt_minio mc alias set local http://localhost:9000 minioadmin minioadmin
docker exec dbt_minio mc ls --recursive local/dbt-bucket/stg/suppliers

# 3. dbt
docker compose logs dbt --tail 30

# 4. Spark ETL + проверка Iceberg
docker exec spark_iceberg /opt/spark/bin/spark-submit /opt/spark/jobs/etl_supply_chain.py
docker exec spark_iceberg /opt/spark/bin/spark-submit /opt/spark/jobs/verify_iceberg.py

# 5. StarRocks external catalog
Get-Content -Raw spark\init-starrocks.sql | docker exec -i starrocks mysql -h 127.0.0.1 -P 9030 -uroot
docker exec starrocks mysql -h 127.0.0.1 -P 9030 -uroot -e "SHOW CATALOGS"
docker exec starrocks mysql -h 127.0.0.1 -P 9030 -uroot -e "SELECT COUNT(*) FROM iceberg_lakehouse.supply_chain.suppliers"

# 6. Airflow
docker exec airflow_scheduler airflow dags list
docker exec airflow_scheduler airflow dags list-import-errors
docker exec airflow_scheduler airflow dags trigger dbt_supply_chain_pipeline
docker exec airflow_scheduler airflow dags list-runs -d dbt_supply_chain_pipeline

# 7. UI
# Airflow:   http://localhost:8080  (admin/admin)
# Superset:  http://localhost:8088  (admin/admin)
# MinIO:     http://localhost:9001  (minioadmin/minioadmin)
# StarRocks: http://localhost:8030
```

---

## 12. Известные ограничения и оставшиеся расхождения

1. **StarRocks без healthcheck** — известное ограничение README, не исправлялось.
2. **dbt-starrocks 1.6.2** — зафиксирован, не обновлялся (по README).
3. **Iceberg REST fixture** — метаданные каталога хранятся в SQLite
   `/tmp/iceberg_catalog.db` внутри контейнера. После `docker compose down`
   (пересоздание контейнера) каталог Iceberg пуст: нужно повторно выполнить
   `etl_supply_chain.py`. Определение `iceberg_lakehouse` в StarRocks сохраняется
   в volume `starrocks_data`. Это ограничение fixture, описано в README.
4. **MOEX-модели** — фактически 16 stg + 7 mart вместо 15+6; 9 тестов проходят.
5. **Maven-зависимости Spark** — первый запуск скачал ~324 МБ
   (`aws-java-sdk-bundle`), а не ~70 МБ, как указано в README.
6. **Airflow provider dependency warning** — в базовом образе после установки
   dbt остаётся предупреждение pip: часть неиспользуемых providers требует
   `apache-airflow-providers-common-sql>=1.20`, установлена 1.10.1. На ядро
   Airflow, DAG и BashOperator не влияет; `airflow dags list-import-errors` пуст.
   Для полного устранения нужно вынести dbt в отдельный venv внутри образа
   (не делалось, чтобы не менять рабочую схему DAG).
7. **`airflow/dags/spark_etl_dag.py` отсутствует** — README его описывает, но
   DAG требует доступа к `docker.sock` и не входит в обязательный пайплайн.
   Не добавлялся, чтобы не создавать заведомо нерабочий DAG.
8. **`airflow/requirements.txt` отсутствует** — зависимости ставятся в
   `airflow/Dockerfile`; README ссылается на файл, которого нет.
9. **`superset-worker` использует Redis Airflow** (db 2/3). В полном стеке это
   работает; в Superset-only режиме worker не запускается.
10. **Артефакты запуска** — `project/target`, `project/logs`, `airflow/logs`
    изменены проверочными запусками. Это не ручные правки.

---

## 13. Итоговый статус

**READY WITH LIMITATIONS.**

Все обязательные проверки выполнены:

- Trino/Hive в коде и Docker отсутствуют;
- `docker compose up -d --build` проходит;
- критичные сервисы запущены и healthy (кроме задокументированных без healthcheck);
- dbt run/test проходят;
- Airflow DAG виден, импортируется и успешно выполняется;
- Spark + Iceberg работают;
- StarRocks читает Iceberg через external catalog;
- отчёты `AUDIT_REPORT.md` и `REPORT_DOCKER_FIX.md` созданы.

Ограничения перечислены в разделе 12 и не блокируют использование проекта.
