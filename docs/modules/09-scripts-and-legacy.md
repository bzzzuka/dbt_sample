# Модуль 09 — скрипты и legacy

**Файлы:** `scripts/windows/*.ps1`, `scripts/linux/*.sh`,
`scripts/common.ps1`, `scripts/common.sh`, `scripts/README.md`,
`make_stg.ps1`.

---

## 1. Общие helper'ы

- `scripts/common.ps1` — функции Windows;
- `scripts/common.sh` — функции Linux/macOS.

Они проверяют Docker, `docker compose config`, ждут one-shot/healthcheck.

---

## 2. Windows

```powershell
.\scripts\windows\start-all.ps1
.\scripts\windows\start-airflow.ps1
.\scripts\windows\start-superset.ps1
.\scripts\windows\stop.ps1
```

---

## 3. Linux/macOS

```bash
chmod +x scripts/linux/*.sh
./scripts/linux/start-all.sh
./scripts/linux/start-airflow.sh
./scripts/linux/start-superset.sh
./scripts/linux/stop.sh
```

Для Apple Silicon:

```bash
USE_AMD64=1 ./scripts/linux/start-all.sh
```

---

## 4. Legacy

- `setup_starrocks.py` — **удалён** (генератор старой StarRocks-версии);
- `make_dag.py` — **удалён** (старый StarRocks DAG);
- `make_stg.ps1` — пустой файл, безвреден.

---

## 5. Удалённые StarRocks-файлы

- `dbt/scripts/load_s3_to_starrocks.py`;
- `dbt/scripts/load_retail_to_starrocks.py`;
- `spark/init-starrocks.sql`;
- `dbt-starrocks` в образах;
- `add_starrocks_db.py`;
- `create_dashboard.py` (legacy);
- `starrocks` service/volume.

---

## 6. Проверка

```powershell
docker compose config --quiet
docker compose ps -a
```

---

## 7. Связанные документы

- [`../RUNBOOK.md`](../RUNBOOK.md)
- [`../BUILD.md`](../BUILD.md)
