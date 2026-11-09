# Модуль 09 — скрипты, legacy-файлы и отчёты

**Файлы модуля:**

- `scripts/windows/start-all.ps1`, `start-airflow.ps1`, `start-superset.ps1`,
  `stop.ps1`
- `scripts/linux/start-all.sh`, `start-airflow.sh`, `start-superset.sh`,
  `stop.sh`
- `scripts/common.ps1`, `scripts/common.sh`, `scripts/README.md`
- `docker-compose.mac-amd64.yml`
- `make_dag.py`
- `setup_starrocks.py`
- `make_stg.ps1`
- `.env`, `.gitignore`
- `AUDIT_REPORT.md`, `REPORT_DOCKER_FIX.md`, `REPORT_ITERATION_2.md`
- README внутри модулей

---

## 1. Start-скрипты

### `scripts/windows/start-all.ps1`

Запускает полный стек:

- StarRocks, MinIO, Redis;
- `data-init`, `dbt`;
- Superset + dashboards;
- Airflow init + webserver/scheduler/worker/triggerer.

```powershell
.\scripts\windows\start-all.ps1
```

Скрипт использует `scripts/common.ps1`, проверяет `docker compose config`,
ждёт one-shot и healthcheck.

### `scripts/windows/start-airflow.ps1`

Режим «Airflow без Superset», включая `airflow-worker`.

```powershell
.\scripts\windows\start-airflow.ps1
```

### `scripts/windows/start-superset.ps1`

Режим «Superset без Airflow», включая `superset-worker`.

```powershell
.\scripts\windows\start-superset.ps1
```

### `scripts/windows/stop.ps1`

Останавливает проект, volumes сохраняются.

```powershell
.\scripts\windows\stop.ps1
```

### Linux/macOS-скрипты

Для Linux/macOS отдельные bash-скрипты в `scripts/linux/`, общие функции — в
`scripts/common.sh`:

| Скрипт | Что делает |
|---|---|
| `scripts/common.sh` | общие функции: `dc`, ожидание healthcheck, one-shot, StarRocks |
| `scripts/linux/start-all.sh` | полный стек, включая `airflow-worker` и `superset-worker` |
| `scripts/linux/start-airflow.sh` | Airflow без Superset, включая `airflow-worker` |
| `scripts/linux/start-superset.sh` | Superset без Airflow, включая `superset-worker` |
| `scripts/linux/stop.sh` | `docker compose stop`, volumes сохраняются |

Запуск:

```bash
chmod +x scripts/linux/*.sh
./scripts/linux/start-all.sh
```

Fallback для Apple Silicon:

```bash
USE_AMD64=1 ./scripts/linux/start-all.sh
```

Он подключает `docker-compose.mac-amd64.yml` и запускает StarRocks,
Iceberg REST и Spark как `linux/amd64`. Требуется Rosetta.

---

## 2. `make_dag.py` — legacy-генератор DAG

**Не запускать на актуальном проекте.**

Что делает:

- пишет `airflow/dags/dbt_supply_chain_dag.py` с **4 задачами**:
  `generate_and_upload -> load_to_starrocks -> dbt_run -> dbt_test`;
- не содержит `generate_retail` и `load_retail_to_starrocks`;
- использует старый `ENV`.

Если запустить, retail-задачи исчезнут из DAG. Восстановить можно только
из git или вручную.

---

## 3. `setup_starrocks.py` — legacy-генератор всего проекта

**Не запускать.**

Это самый опасный файл в корне. Он перезаписывает:

- `.env`;
- `docker-compose.yml`;
- `dbt/Dockerfile`;
- `dbt/profiles/profiles.yml`;
- `dbt/scripts/init.sh`;
- `dbt/scripts/run_dbt.sh`;
- `dbt/scripts/load_s3_to_starrocks.py`;
- `project/models/staging/stg_*.sql`;
- `project/models/staging/sources.yml`;
- `project/models/marts/mart_*.sql`;
- `project/models/marts/schema.yml`;
- `project/dbt_project.yml`.

При этом он описывает **старую архитектуру**:

- StarRocks FE и BE как отдельные сервисы (`starrocks-fe`, `starrocks-be`);
- dbt 1.9.0 вместо 1.6.2;
- нет Superset;
- нет Airflow;
- нет retail;
- нет Iceberg REST.

Запуск `python setup_starrocks.py` сломает текущий проект. Если он нужен
для истории — запускайте только в отдельной копии репозитория.

---

## 4. `make_stg.ps1`

Пустой файл (0 байт). Исторический артефакт. Ничего не делает.

---

## 5. `.env`

Локальные переменные Compose. Основные группы:

- StarRocks;
- MinIO;
- генерация supply chain;
- Superset;
- Airflow;
- MOEX (опционально).

Подробно — [`01-infrastructure.md`](01-infrastructure.md).

Не коммитьте реальные секреты. Для локального учебного проекта текущие
значения допустимы.

---

## 6. `.gitignore`

Игнорируются:

- логи (`airflow/logs`, `project/logs`, `*.log`);
- dbt-артефакты (`project/target`, `target`, `dbt_packages`);
- Python-кэши (`__pycache__`, `*.pyc`, `.pytest_cache`, `.mypy_cache`,
  `.ruff_cache`);
- виртуальные окружения;
- `node_modules`;
- `dbt/profiles/.user.yml`;
- `.env.local`;
- IDE/OS-файлы;
- `.ivy2`.

Если артефакт уже в индексе, `.gitignore` его не уберёт. Нужно:

```powershell
git rm -r --cached <path>
git commit -m "chore: untrack runtime artifacts"
```

---

## 7. Отчёты

| Файл | Что содержит |
|---|---|
| `AUDIT_REPORT.md` | Первый аудит проекта, найденные проблемы |
| `REPORT_DOCKER_FIX.md` | Первая итерация исправлений, проверки сервисов |
| `REPORT_ITERATION_2.md` | Airflow auth, retail data, Superset dashboards |

Это **исторические документы**, не инструкции по эксплуатации. Они
полезны, чтобы понять, какие проблемы уже встречались и как чинились.

---

## 8. README внутри модулей

| Файл | Состояние |
|---|---|
| `README.md` (корень) | Общий обзор, но числа устарели (15+6, без retail) |
| `airflow/README.md` | Подробный, но местами устарел (`requirements.txt`, 4 задачи, `spark_etl_dag`) |
| `dbt/README.md` | Описывает базовый supply chain |
| `spark/README.md` | Хорошее объяснение Spark/Iceberg |
| `superset/README.md` | Описывает старый `create_dashboard.py` |

Актуальная документация — `docs/`. Если README противоречит `docs/`,
верьте `docs/` и фактическим файлам.

---

## 9. Что безопасно запускать

| Команда | Безопасно? |
|---|---|
| `docker compose up -d --build` | Да |
| `docker compose ps -a` | Да |
| `docker compose logs ...` | Да |
| `docker compose run ... dbt ...` | Да |
| `docker exec ... airflow ...` | Да |
| `.\scripts\windows\start-all.ps1` | Да (Windows) |
| `.\scripts\windows\start-airflow.ps1` | Да (Windows) |
| `.\scripts\windows\start-superset.ps1` | Да (Windows) |
| `.\scripts\windows\stop.ps1` | Да (Windows) |
| `./scripts/linux/start-all.sh` | Да (Linux/macOS) |
| `./scripts/linux/start-airflow.sh` | Да (Linux/macOS) |
| `./scripts/linux/start-superset.sh` | Да (Linux/macOS) |
| `./scripts/linux/stop.sh` | Да |
| `USE_AMD64=1 ./scripts/linux/start-all.sh` | Да, если включена Rosetta |
| `python setup_starrocks.py` | **Нет** |
| `python make_dag.py` | **Нет** |
| `make_stg.ps1` | Безвредно, но бесполезно |
| `docker compose down -v` | Только для полного сброса |

---

## 10. Связанные документы

- [`../RUNBOOK.md`](../RUNBOOK.md)
- [`../DEVELOPMENT_GUIDE.md`](../DEVELOPMENT_GUIDE.md)
- [`01-infrastructure.md`](01-infrastructure.md)
- [`03-dbt.md`](03-dbt.md)
