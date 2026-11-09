# RUNBOOK — как запускать и проверять проект

**Актуально на:** 2026-11-09  
**Главный файл по эксплуатации.** Если нужно просто поднять проект — читайте
его сверху вниз.

---

## 0. Перед первым запуском

### 0.1. Проверить Docker

```powershell
docker version
docker compose version
docker info | Select-String "Total Memory"
```

Нужно:

- Docker Desktop / Docker Engine;
- Docker Compose v2;
- минимум 8 ГБ ОЗУ (лучше 16 ГБ);
- ~15 ГБ диска.

### 0.2. Проверить `.env`

```powershell
Get-Content .env
```

Ключевые значения:

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

`AIRFLOW_FERNET_KEY` должен быть валидным Fernet-ключом (44 символа base64).
`AIRFLOW__WEBSERVER__SECRET_KEY` — любая непустая стабильная строка. Оба
значения должны быть одинаковыми для всех Airflow-сервисов.

### 0.3. PowerShell

Если скрипты не запускаются:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

В PowerShell скрипт запускается с `.\`:

```powershell
.\scripts\windows\start-all.ps1
```

---

## 1. Полный запуск (рекомендуется)

```powershell
docker compose config
docker compose up -d --build
docker compose ps -a
```

Почему именно так:

- `docker compose config` проверяет YAML и подстановку `.env`;
- `--build` собирает Airflow, dbt и Superset;
- `up -d` поднимает все сервисы и учитывает healthcheck/depends_on.

Первый запуск может занять 5–15 минут:

- собираются образы;
- Spark при первом ETL скачивает Maven-зависимости (фактически ~300+ МБ,
  кэш в `/tmp/.ivy2`);
- `data-init` генерирует 15 supply-chain таблиц и 11 retail-таблиц.

### 1.1. Ожидаемое состояние

`docker compose ps -a`:

| Тип | Сервисы | Ожидаемый статус |
|---|---|---|
| Long-running | starrocks, minio, superset, superset-worker, postgres-airflow, redis, airflow-webserver, airflow-scheduler, airflow-worker, airflow-triggerer, iceberg-rest, spark-iceberg | `Up` |
| Healthy | minio, superset, superset-worker, postgres-airflow, redis, airflow-webserver, airflow-worker, iceberg-rest | `Up (healthy)` |
| Без healthcheck | starrocks, spark-iceberg, airflow-scheduler, airflow-triggerer | `Up`, это нормально |
| One-shot | airflow-init, data-init, dbt, superset-init, superset-dashboards | `Exited (0)` |

> `Exited (0)` у one-shot сервисов — **успех**, а не падение.
> `Exited (1+)` — ошибка, смотрите `docker compose logs <service>`.

### 1.2. Проверить health endpoints

```powershell
Invoke-WebRequest -UseBasicParsing http://localhost:8080/health | Select-Object StatusCode
Invoke-WebRequest -UseBasicParsing http://localhost:8088/health | Select-Object StatusCode
Invoke-WebRequest -UseBasicParsing http://localhost:8181/v1/config | Select-Object StatusCode
Invoke-WebRequest -UseBasicParsing http://localhost:9000/minio/health/live | Select-Object StatusCode
```

Ожидаемо `200`.

---

## 2. Интерфейсы и доступы

| Сервис | URL | Логин | Пароль | Назначение |
|---|---|---|---|---|
| Airflow | http://localhost:8080 | admin | admin | Оркестрация |
| Superset | http://localhost:8088 | admin | admin | BI |
| MinIO Console | http://localhost:9001 | minioadmin | minioadmin | S3 UI |
| MinIO S3 API | http://localhost:9000 | minioadmin | minioadmin | S3 API |
| StarRocks FE | http://localhost:8030 | root | (пусто) | OLAP UI |
| StarRocks SQL | `localhost:9030` | root | (пусто) | MySQL-протокол |
| Iceberg REST | http://localhost:8181 | — | — | Catalog |
| Spark UI | http://localhost:4040 | — | — | Только во время job |

Подключение из DBeaver к StarRocks:

- Type: **MySQL**
- Host: `localhost`
- Port: `9030`
- User: `root`
- Password: пусто
- Database: `analytics`

---

## 3. Первый запуск пайплайна

### 3.1. Airflow: снять DAG с паузы

Новые DAG создаются на паузе (`AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION=True`).

```powershell
docker exec airflow_scheduler airflow dags list
docker exec airflow_scheduler airflow dags unpause dbt_supply_chain_pipeline
docker exec airflow_scheduler airflow dags trigger dbt_supply_chain_pipeline
```

Проверить импорт DAG:

```powershell
docker exec airflow_scheduler airflow dags list-import-errors
```

Ожидаемо: `No data found`.

Проверить запуски:

```powershell
docker exec airflow_scheduler airflow dags list-runs -d dbt_supply_chain_pipeline
```

Проверить задачи конкретного запуска:

```powershell
docker exec airflow_scheduler airflow tasks states-for-dag-run `
  dbt_supply_chain_pipeline manual__2026-11-08T14:02:46+00:00
```

Ожидаемо: все 6 задач `success`:

```
generate_and_upload
load_to_starrocks
generate_retail
load_retail_to_starrocks
dbt_run
dbt_test
```

### 3.2. dbt вручную

Сервис `dbt` — one-shot. Он уже запускался при `docker compose up`.
Посмотреть результат:

```powershell
docker compose logs dbt --tail 100
```

Запустить произвольную dbt-команду:

```powershell
docker compose run --rm --no-deps --entrypoint dbt dbt `
  --profiles-dir /dbt/profiles run

docker compose run --rm --no-deps --entrypoint dbt dbt `
  --profiles-dir /dbt/profiles test

docker compose run --rm --no-deps --entrypoint dbt dbt `
  --profiles-dir /dbt/profiles run --select "stg_retail__*"

docker compose run --rm --no-deps --entrypoint dbt dbt `
  --profiles-dir /dbt/profiles run --select "mart_retail__*"
```

> Не используйте `docker compose run dbt dbt run` без `--entrypoint dbt`:
> у сервиса `dbt` entrypoint — `/dbt/scripts/run_dbt.sh`, и аргументы
> `dbt run` будут проигнорированы/перепутаны.

Полный прогон через entrypoint:

```powershell
docker compose run --rm --no-deps dbt
```

Он выполнит `dbt debug`, `dbt run`, `dbt test`.

### 3.3. StarRocks: проверить данные

```powershell
docker exec starrocks mysql -h 127.0.0.1 -P 9030 -uroot -e "USE analytics; SHOW TABLES;"

docker exec starrocks mysql -h 127.0.0.1 -P 9030 -uroot -e "SELECT COUNT(*) FROM analytics.raw_suppliers;"
docker exec starrocks mysql -h 127.0.0.1 -P 9030 -uroot -e "SELECT COUNT(*) FROM analytics.raw_retail_orders;"
docker exec starrocks mysql -h 127.0.0.1 -P 9030 -uroot -e "SELECT COUNT(*) FROM analytics.mart_retail__sales_by_month;"
```

Ожидаемые ориентиры:

| Таблица | Строк |
|---|---:|
| `raw_suppliers` | 5000 |
| `raw_retail_orders` | 5000 |
| `mart_retail__sales_by_month` | 13 |
| `mart_retail__top_products` | 500 |
| `mart_retail__customer_ltv` | 3000 |
| `mart_supplier_performance` | 5000 |

### 3.4. MinIO: проверить файлы

`mc` внутри контейнера не имеет сохранённого alias `local` после пересоздания.
Настройте его:

```powershell
docker exec dbt_minio mc alias set local http://localhost:9000 minioadmin minioadmin
docker exec dbt_minio mc ls local/dbt-bucket
docker exec dbt_minio mc ls --recursive local/dbt-bucket/stg/suppliers
docker exec dbt_minio mc ls --recursive local/dbt-bucket/retail/stg/orders
```

Ожидаемо:

```
stg/suppliers/{date}/suppliers_part_001.csv
retail/stg/orders/{date}/orders_part_001.csv
```

### 3.5. Spark + Iceberg

```powershell
docker exec spark_iceberg /opt/spark/bin/spark-submit /opt/spark/jobs/etl_supply_chain.py
docker exec spark_iceberg /opt/spark/bin/spark-submit /opt/spark/jobs/verify_iceberg.py
```

Ожидаемо:

- `Прочитано: 5000 строк, 121 колонок`;
- namespace `supply_chain`;
- таблица `suppliers`;
- `COUNT(*) = 5000`.

Первый запуск скачивает Maven-зависимости, это нормально.

### 3.6. StarRocks external catalog

Создать каталог (идемпотентно):

```powershell
Get-Content -Raw spark\init-starrocks.sql | docker exec -i starrocks mysql `
  -h 127.0.0.1 -P 9030 -uroot
```

Проверить:

```powershell
docker exec starrocks mysql -h 127.0.0.1 -P 9030 -uroot -e "SHOW CATALOGS;"
docker exec starrocks mysql -h 127.0.0.1 -P 9030 -uroot -e "SHOW DATABASES FROM iceberg_lakehouse;"
docker exec starrocks mysql -h 127.0.0.1 -P 9030 -uroot -e "SHOW TABLES FROM iceberg_lakehouse.supply_chain;"
docker exec starrocks mysql -h 127.0.0.1 -P 9030 -uroot -e "SELECT COUNT(*) FROM iceberg_lakehouse.supply_chain.suppliers;"
```

Ожидаемо: каталог `iceberg_lakehouse`, база `supply_chain`, таблица
`suppliers`, `5000` строк.

### 3.7. Superset

1. Открыть http://localhost:8088.
2. Войти `admin/admin`.
3. Открыть `Supply Chain Overview`.
4. Открыть `Retail Overview`.

Проверить, что дашборды созданы:

```powershell
$login = Invoke-RestMethod -Method Post `
  -Uri http://localhost:8088/api/v1/security/login `
  -ContentType 'application/json' `
  -Body '{"username":"admin","password":"admin","provider":"db","refresh":true}'

$h = @{ Authorization = "Bearer $($login.access_token)" }
Invoke-RestMethod -Uri http://localhost:8088/api/v1/dashboard/ -Headers $h |
  Select-Object -ExpandProperty result |
  Select-Object id, dashboard_title, published
```

Ожидаемо: 2 дашборда, `published=True`.

---

## 4. Режимы запуска (Windows/Linux/macOS)

Скрипты используют общие helper'ы (`scripts/common.ps1` и
`scripts/common.sh`), проверяют `docker compose config`, ждут завершения
one-shot сервисов и healthcheck. Полный `docker compose up -d` также
подходит, если не нужны обёртки.

### 4.1. `scripts/windows/start-all.ps1`

Запускает StarRocks, MinIO, Redis, data-init, dbt, Superset, дашборды и
Airflow (webserver, scheduler, worker, triggerer).

```powershell
.\scripts\windows\start-all.ps1
```

### 4.2. `scripts/windows/start-airflow.ps1`

Режим «Airflow без Superset»: StarRocks, MinIO, data-init, dbt, Postgres,
Redis, Airflow, включая `airflow-worker`.

```powershell
.\scripts\windows\start-airflow.ps1
```

### 4.3. `scripts/windows/start-superset.ps1`

Режим «Superset без Airflow»: StarRocks, MinIO, Redis, data-init, dbt,
Superset, дашборды, включая `superset-worker`.

```powershell
.\scripts\windows\start-superset.ps1
```

### 4.4. Linux/macOS

PowerShell-скрипты не нужны. Есть отдельные bash-скрипты:

```bash
chmod +x scripts/linux/*.sh
./scripts/linux/start-all.sh
./scripts/linux/start-airflow.sh
./scripts/linux/start-superset.sh
./scripts/linux/stop.sh
```

Они ждут завершения one-shot сервисов и healthcheck, включают нужные
worker'ы. Подробная сборка на Windows/Linux/macOS — [`BUILD.md`](BUILD.md).

Fallback для Apple Silicon:

```bash
USE_AMD64=1 ./scripts/linux/start-all.sh
```

Либо напрямую:

```bash
docker compose up -d --build
```

---

## 5. Ежедневные команды

### 5.1. Статус и логи

```powershell
docker compose ps -a
docker compose logs --tail=100 airflow-webserver
docker compose logs -f airflow-scheduler
docker compose logs --tail=100 dbt
docker compose logs --tail=100 superset-dashboards
```

### 5.2. Перезапуск одного сервиса

```powershell
docker compose restart airflow-scheduler
docker compose up -d --force-recreate airflow-worker
```

### 5.3. Пересборка после изменения Dockerfile

```powershell
docker compose build airflow-init
docker compose up -d --force-recreate airflow-webserver airflow-scheduler airflow-worker airflow-triggerer

docker compose build dbt data-init
docker compose up -d data-init dbt

docker compose build superset superset-init superset-worker superset-dashboards
docker compose up -d superset superset-worker superset-dashboards
```

### 5.4. Что применять после изменений

| Что изменили | Что сделать |
|---|---|
| DAG-файл в `airflow/dags/` | `docker compose restart airflow-scheduler airflow-webserver airflow-worker` |
| Скрипт в `dbt/scripts/` | Airflow читает его через volume; для `data-init`/`dbt` пересобрать образы `dbt` и `data-init` |
| dbt-модель в `project/models/` | `dbt run` (или перезапустить DAG) |
| `dbt/profiles/profiles.yml` | Перезапустить Airflow-сервисы; для `dbt`-образа пересобрать `dbt` |
| `spark/conf/*` | Перезапустить `spark-iceberg` |
| `superset/init/*` | `docker compose up -d --force-recreate superset-dashboards` |
| `superset/superset_config.py` | Пересоздать Superset-сервисы |
| `.env` | Пересоздать затронутые сервисы (`docker compose up -d --force-recreate ...`) |
| `docker-compose.yml` | `docker compose config` → `docker compose up -d` |

---

## 6. Остановка и очистка

### Остановить, сохранить данные

```powershell
docker compose stop

# или обёртки:
.\scripts\windows\stop.ps1          # Windows
./scripts/linux/stop.sh             # Linux/macOS

# или (удаляет контейнеры, но не volumes):
docker compose down
```

`down` удаляет контейнеры и сеть, но **не** volumes.

### Полный сброс (удалить данные)

```powershell
docker compose down -v
docker compose up -d --build
```

> `-v` удаляет `starrocks_data`, `minio_data`, `superset_home`,
> `postgres_airflow_data`. Все сгенерированные данные, дашборды и история
> Airflow будут потеряны. Используйте только для чистого старта.

### Пересоздать только один сервис

```powershell
docker compose up -d --force-recreate airflow-webserver
```

---

## 7. Airflow: вход и авторизация

### Нормальный вход

- URL: http://localhost:8080
- Логин: `admin`
- Пароль: `admin`

### Если `admin/admin` не работает

Сначала проверьте пользователя и БД:

```powershell
docker exec airflow_webserver airflow users list
docker exec airflow_webserver airflow db check
```

Проверьте хеш пароля:

```powershell
docker exec airflow_postgres psql -U airflow -d airflow `
  -c "SELECT username, substr(password,1,20) AS prefix, active FROM ab_user;"
```

Если префикс `scrypt:...`, а Airflow 2.10.5 использует Werkzeug 2.2.3,
будет ошибка:

```
ValueError: unsupported hash type scrypt:32768:8:1
```

Исправление — сбросить пароль под текущий Werkzeug:

```powershell
docker exec airflow_webserver airflow users reset-password `
  --username admin --password admin
```

После этого хеш станет `pbkdf2:sha256:...`, вход заработает.

Если `admin` отсутствует:

```powershell
docker exec airflow_webserver airflow users create `
  --username admin --password admin `
  --firstname Admin --lastname User `
  --role Admin --email admin@example.com
```

Проверьте, что ключи одинаковые:

```powershell
docker exec airflow_webserver env | Select-String "SECRET_KEY|FERNET"
docker exec airflow_scheduler env | Select-String "SECRET_KEY|FERNET"
```

`AIRFLOW__WEBSERVER__SECRET_KEY` должен совпадать. Если он менялся —
старые сессии/CSRF-токены станут недействительны, это ожидаемо.

---

## 8. Troubleshooting

| Симптом | Причина | Решение |
|---|---|---|
| `env: 'bash\r': No such file or directory` | CRLF в `.sh` | Перевести файл в LF (VS Code: CRLF → LF) |
| `set: -: invalid option` | CRLF в `.sh` | То же |
| `Bad Request` / `500` при логине Airflow | scrypt-хеш пароля | `airflow users reset-password ...` |
| Порт 8080 занят | старый контейнер | `Get-NetTCPConnection -LocalPort 8080`; удалить старый контейнер |
| `Exited (137)` | OOM | Увеличить память Docker / запускать по режимам |
| `dbt: command not found` в Airflow | PATH | Проверить `PATH` в DAG `ENV` |
| `dbt` не подключается к StarRocks | profiles/пароль/порт | `dbt debug`, проверить `profiles.yml` и `.env` |
| `Column 'X' is ambiguous` | JOIN без алиасов | Использовать `ON a.col = b.col` |
| `scheme is null` в `FILES()` | MinIO path-style | `aws.s3.enable_path_style_access=true` |
| StarRocks не видит Iceberg | каталог не создан / REST пуст | `init-starrocks.sql`, затем Spark ETL |
| `Results backend is not configured` в Superset | нет Redis results backend | Проверить `superset_config.py`, Redis, пересоздать Superset |
| Superset worker unhealthy | healthcheck/Redis | Проверить `docker compose logs superset-worker` |
| DAG `queued`, но не выполняется | нет worker | `docker compose up -d airflow-worker` |
| Airflow DAG не появился | import error | `airflow dags list-import-errors` |
| Spark долго стартует | качает Maven | Подождать, кэш `/tmp/.ivy2` |
| `NoSuchNamespaceException` в Iceberg | REST потерял метаданные | Повторно запустить `etl_supply_chain.py` |
| `docker compose up` падает на healthcheck | сервис ещё стартует | `docker compose ps -a`, логи, подождать |

### Полезные диагностические команды

```powershell
docker compose config
docker compose ps -a
docker stats --no-stream
docker compose logs --tail=200 <service>
docker exec <container> bash
```

---

## 9. Что считать успешным запуском

- `docker compose ps -a` — long-running сервисы `Up`, healthy там, где есть
  healthcheck;
- Airflow `admin/admin` пускает, DAG `dbt_supply_chain_pipeline` виден;
- DAG run: 6 задач `success`;
- dbt: `PASS=39`, `PASS=19`;
- StarRocks: `raw_suppliers=5000`, `raw_retail_orders=5000`,
  `mart_retail__sales_by_month=13`;
- Spark: Iceberg `suppliers=5000`;
- StarRocks external catalog: `iceberg_lakehouse` + `5000`;
- Superset: 2 дашборда, 16 чартов, страницы открываются.

---

## 10. Чего не делать

1. Не запускайте `python setup_starrocks.py` — он перезапишет актуальный
   `docker-compose.yml`, dbt-файлы и вернёт старую архитектуру.
2. Не запускайте `python make_dag.py` — он перезапишет DAG версией без retail.
3. Не коммитьте `airflow/logs`, `project/logs`, `project/target`,
   `__pycache__`, `.user.yml` — они в `.gitignore`.
4. Не делайте `docker compose down -v`, если не хотите потерять данные.
5. Не отключайте CSRF в Airflow как «быстрый фикс» — чините причину.
6. Не обновляйте dbt-starrocks до 1.7+ без проверки совместимости.
