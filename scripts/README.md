# scripts — Windows / Linux helper scripts

Единая папка для скриптов запуска. Windows и POSIX-скрипты разделены, общие
helper'ы лежат в корне `scripts/`.

```
scripts/
├── README.md       # этот файл
├── common.ps1      # общие функции Windows/PowerShell
├── common.sh       # общие функции Linux/macOS (bash)
├── windows/
│   ├── start-all.ps1
│   ├── start-airflow.ps1
│   ├── start-superset.ps1
│   └── stop.ps1
└── linux/
    ├── start-all.sh
    ├── start-airflow.sh
    ├── start-superset.sh
    └── stop.sh
```

Скрипты сами находят корень проекта, поэтому запускать их можно из любой
директории.

---

## Windows

Требования:

- Docker Desktop с WSL2;
- Docker Compose v2 (`docker compose`);
- PowerShell 5.1+;
- 8+ ГБ RAM для Docker.

Запуск:

```powershell
.\scripts\windows\start-all.ps1
```

Режимы:

```powershell
.\scripts\windows\start-all.ps1
.\scripts\windows\start-airflow.ps1
.\scripts\windows\start-superset.ps1
.\scripts\windows\stop.ps1
```

Если PowerShell блокирует скрипты:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

Windows-скрипты используют `scripts/common.ps1`:

- `Assert-Docker`;
- `Invoke-Compose`;
- `Wait-Healthy`;
- `Wait-OneShot`;
- `Wait-StarRocks`;
- `Write-Access`.

`scripts/windows/start-all.ps1` включает `airflow-worker` и `superset-worker`.
`scripts/windows/start-airflow.ps1` включает `airflow-worker`.
`scripts/windows/start-superset.ps1` включает `superset-worker`.
`scripts/windows/stop.ps1` останавливает проект, volumes сохраняются.

---

## Linux / macOS

Требования:

- Docker Engine (Linux) или Docker Desktop (macOS);
- Docker Compose v2 (`docker compose`);
- bash;
- 8+ ГБ RAM для Docker.

Запуск:

```bash
chmod +x scripts/linux/*.sh
./scripts/linux/start-all.sh
```

Режимы:

```bash
./scripts/linux/start-all.sh
./scripts/linux/start-airflow.sh
./scripts/linux/start-superset.sh
./scripts/linux/stop.sh
```

Linux: если `docker` требует sudo, добавьте пользователя в группу:

```bash
sudo usermod -aG docker "$USER"
# затем перелогиньтесь
```

POSIX-скрипты используют `scripts/common.sh`:

- `require_docker`;
- `dc` (обёртка `docker compose`);
- `wait_healthy`;
- `wait_one_shot`;
- `wait_starrocks`;
- `print_access`.

### Apple Silicon fallback

Если arm64-образ StarRocks/Spark/Iceberg REST нестабилен:

```bash
USE_AMD64=1 ./scripts/linux/start-all.sh
```

Нужна Rosetta в Docker Desktop. Будет медленнее.

---

## Что скрипты делают

1. Проверяют Docker/Compose и наличие `.env`.
2. Проверяют `docker compose config`.
3. Поднимают сервисы.
4. Ждут завершения one-shot (`data-init`, `dbt`, `superset-init`,
   `superset-dashboards`, `airflow-init`).
5. Ждут healthcheck (`minio`, `redis`, `superset`, `airflow-*`,
   `iceberg-rest`).
6. Ждут SQL-готовность StarRocks.
7. Печатают URL/логины.

One-shot сервисы должны завершиться с `Exited (0)` — это успех.

---

## Чего скрипты не делают

- не запускают legacy-генераторы `setup_starrocks.py` и `make_dag.py`;
- не удаляют volumes;
- не меняют `.env`;
- не делают `docker compose down -v` (полный сброс — вручную).

Подробная сборка и prerequisites:
[`docs/BUILD.md`](../docs/BUILD.md).
