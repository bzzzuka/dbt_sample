# BUILD — сборка на Windows, Linux и macOS

**Актуально на:** 2026-11-09  
**Главная инструкция по сборке.** Для эксплуатации и проверок после сборки
смотрите [`RUNBOOK.md`](RUNBOOK.md).

---

## 0. Коротко

### Windows

```powershell
# Docker Desktop + WSL2, затем:
docker compose config
docker compose up -d --build
docker compose ps -a
```

Или:

```powershell
.\scripts\windows\start-all.ps1
```

### Linux (Docker Engine)

```bash
# Docker Engine + Compose plugin.
# Официальная инструкция: https://docs.docker.com/engine/install/
# Для локальной машины можно использовать convenience script:
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker "$USER"
# затем перелогиньтесь, чтобы применилась группа docker
```

Затем из корня проекта:

```bash
chmod +x scripts/linux/*.sh
./scripts/linux/start-all.sh
```

### macOS (Intel и Apple Silicon)

```bash
# Docker Desktop for Mac, затем из корня проекта:
chmod +x scripts/linux/*.sh
./scripts/linux/start-all.sh
```

Или напрямую на Linux/macOS:

```bash
docker compose config
docker compose up -d --build
docker compose ps -a
```

> POSIX-скрипты лежат в `scripts/linux/` и работают на Linux и macOS.
> Windows-скрипты лежат в `scripts/windows/`; общие helper'ы —
> `scripts/common.sh` и `scripts/common.ps1`.

---

## 1. Общие требования

| Требование | Минимум | Рекомендуется |
|---|---|---|
| Docker | Desktop 4.30+ (Win/Mac) или Engine + Compose plugin (Linux) | последняя стабильная |
| Docker Compose | v2 (`docker compose`) | v2.20+ |
| ОЗУ для Docker | 8 ГБ | 16 ГБ |
| Свободный диск | 15 ГБ | 40 ГБ |
| Интернет | нужен для первой сборки | стабильный |
| Git | нужен для clone | любой |

Порты, которые должны быть свободны:

```
8080  Airflow
8088  Superset
9000  MinIO S3
9001  MinIO Console
8030  StarRocks FE
9030  StarRocks SQL
8040  StarRocks BE
8181  Iceberg REST
4040  Spark UI (только во время job)
```

На хосте **не нужны**: Python, Java, Node.js, dbt, Spark, Xcode, `make`,
`jq`. Всё собирается и запускается внутри Docker-образов. Нужен только
Docker Desktop и Git (или архив проекта).

---

## 2. Что проверено для Linux/macOS и arm64

Проверка выполнена статически из Windows-окружения: манифесты образов,
PyPI-колёса и line endings. Полный runtime-прогон на физическом Linux/Mac
в этой среде не выполнялся — это нужно подтвердить первым запуском.

### 2.1. Архитектуры Docker-образов

Все образы проекта имеют `linux/arm64` и `linux/amd64`:

| Образ | arm64 | amd64 |
|---|---|---|
| `starrocks/allin1-ubuntu:3.4-latest` | да | да |
| `ghcr.io/coollabsio/minio:latest` | да | да |
| `apache/superset:4.1.2` | да | да |
| `apache/airflow:2.10.5-python3.11` | да | да |
| `apache/spark:3.5.6` | да | да |
| `apache/iceberg-rest-fixture:1.10.1` | да | да |
| `postgres:15-alpine` | да | да |
| `redis:7-alpine` | да | да |

Вывод: на Apple Silicon **не требуется** принудительный `linux/amd64` для
штатной сборки. Rosetta нужна только для fallback-режима.

### 2.2. Python-зависимости на arm64

| Зависимость | Статус на linux/arm64 |
|---|---|
| `dbt-core==1.6.2` | есть arm64-колесо `dbt-extractor` |
| `dbt-starrocks==1.6.2` | pure Python |
| `mysql-connector-python==8.0.33` | нет native aarch64 wheel, но есть `py2.py3-none-any.whl` (pure Python) |
| `mysqlclient` (Superset) | собирается из исходников; в образе есть `default-libmysqlclient-dev`, `libssl-dev`, `build-essential`, `pkg-config` |
| `pandas`, `boto3`, `pymysql`, `requests` | есть arm64/pure wheels |

`mysql-connector-python==8.0.33` на arm64 установится как pure-Python
коннектор. Он совместим с `mysql.connector.connect`, но может быть медленнее
нативного. Для учебного проекта это допустимо.

Если на конкретной машине `dbt debug` упадёт на коннекторе, advanced
fallback — `mysql-connector-python==8.4.0` (есть aarch64 wheel), но это
изменение версии: сначала проверьте `dbt run/test`, не меняйте без причины.

### 2.3. Line endings и скрипты

- Все `.sh` в проекте — LF.
- `.gitattributes` закрепляет LF для `.sh`, `.py`, `.sql`, `.yml`,
  `Dockerfile`, `.env`.
- `.ps1` остаются CRLF для PowerShell 5.1.
- POSIX-скрипты вызываются через `bash`, поэтому executable bit не обязателен;
  но `chmod +x` удобнее.

---

## 3. Windows

### 3.1. Установка Docker

1. Установите Docker Desktop.
2. Включите **WSL2 backend**.
3. Проверьте:

```powershell
docker version
docker compose version
docker info | Select-String "Total Memory"
```

### 3.2. Память WSL2

Файл `C:\Users\<user>\.wslconfig`:

```ini
[wsl2]
memory=8GB
processors=4
swap=2GB
```

Для 16 ГБ хоста можно `memory=12GB`. После изменения:

```powershell
wsl --shutdown
```

и перезапустите Docker Desktop.

### 3.3. PowerShell

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

Скрипты запускаются с `.\`:

```powershell
.\scripts\windows\start-all.ps1
```

### 3.4. Line endings

Если репозиторий был склонирован до добавления `.gitattributes`, выполните:

```powershell
git add --renormalize .
git status
```

Или просто переклонируйте проект. Не запускайте `.sh` из Windows без
LF-нормализации.

### 3.5. Запуск

Полный стек:

```powershell
docker compose config
docker compose up -d --build
docker compose ps -a
```

Или `.\scripts\windows\start-all.ps1`.

Режимы:

```powershell
.\scripts\windows\start-airflow.ps1    # Airflow без Superset
.\scripts\windows\start-superset.ps1   # Superset без Airflow
```

Windows-скрипты используют общий `scripts/common.ps1`, проверяют
`docker compose config`, ждут healthcheck и one-shot сервисы:

- `scripts/windows/start-all.ps1` — полный стек, включая `airflow-worker` и `superset-worker`;
- `scripts/windows/start-airflow.ps1` — Airflow без Superset, включая `airflow-worker`;
- `scripts/windows/start-superset.ps1` — Superset без Airflow, включая `superset-worker`.

Либо используйте полный `docker compose up -d`.

### 3.6. Доступы

| Сервис | URL | Логин / пароль |
|---|---|---|
| Airflow | http://localhost:8080 | admin / admin |
| Superset | http://localhost:8088 | admin / admin |
| MinIO | http://localhost:9001 | minioadmin / minioadmin |
| StarRocks FE | http://localhost:8030 | root / (пусто) |

---

## 4. Linux и macOS

### 4.0. Linux (Docker Engine)

Linux не требует Docker Desktop. Нужны Docker Engine, Compose plugin и
права на Docker socket.

```bash
# Docker Engine + Compose plugin.
# Официальная инструкция: https://docs.docker.com/engine/install/
# Для локальной машины:
curl -fsSL https://get.docker.com | sudo sh
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
# перелогиньтесь, чтобы группа применилась
```

Проверка:

```bash
docker version
docker compose version
docker info | grep -i "Total Memory"
```

Если `docker` требует `sudo` — группа `docker` не применилась. Не
запускайте весь проект через `sudo`; настройте группу.

Дальше используйте `scripts/linux/*.sh` (раздел 4.4) или
`docker compose up -d --build`.

### 4.1. macOS: Intel или Apple Silicon

| Mac | Что делать |
|---|---|
| Intel | обычная сборка amd64 |
| Apple Silicon (M1/M2/M3/M4) | обычная сборка arm64; fallback amd64 — только если arm64-образ нестабилен |

### 4.2. Установка Docker на macOS

Установите **Docker Desktop for Mac** (вариант для Apple Chip или Intel).
Запустите Docker Desktop и дождитесь статуса Running.

Проверьте:

```bash
docker version
docker compose version
docker info | grep -i "Total Memory"
```

### 4.3. Настройки Docker Desktop

1. **Resources**: минимум 8 ГБ RAM, лучше 12–16 ГБ; CPU 4+.
2. **Disk image size**: 40+ ГБ.
3. **File sharing**: проект должен лежать в доступной папке, например
   `~/Projects/dbt_sample`.
4. Не размещайте проект в iCloud Drive, OneDrive, Dropbox или на сетевом
   диске — возможны проблемы с bind mounts и правами.
5. **Rosetta** (только для fallback): Settings → General → включить
   «Use Rosetta for x86/amd64 emulation».

### 4.4. Проект и скрипты (Linux/macOS)

```bash
git clone <repo-url> dbt_sample
cd dbt_sample

chmod +x scripts/linux/*.sh
```

Запуск:

```bash
./scripts/linux/start-all.sh
```

Если zsh ругается на права:

```bash
bash scripts/linux/start-all.sh
```

### 4.5. Режимы

```bash
./scripts/linux/start-all.sh       # весь стек
./scripts/linux/start-airflow.sh   # Airflow без Superset
./scripts/linux/start-superset.sh  # Superset без Airflow
./scripts/linux/stop.sh            # остановить, volumes сохранить
```

В отличие от Windows-скриптов, POSIX-скрипты (Linux/macOS):

- `start-all.sh` включает оба worker (`airflow-worker` и `superset-worker`);
- `start-airflow.sh` включает `airflow-worker`;
- `start-superset.sh` включает `superset-worker`;
- ждут завершения one-shot сервисов;
- ждут healthcheck;
- используют `docker compose config` перед запуском;
- поддерживают `USE_AMD64=1` для fallback.

### 4.6. Apple Silicon fallback (если arm64-образ нестабилен)

```bash
USE_AMD64=1 ./scripts/linux/start-all.sh
```

Это добавит `docker-compose.mac-amd64.yml` и запустит `starrocks`,
`iceberg-rest`, `spark-iceberg` как `linux/amd64`. Требуется Rosetta и
больше RAM; будет медленнее. Если нестабилен другой сервис, добавьте его
имя и `platform: linux/amd64` в `docker-compose.mac-amd64.yml`.

Проверить, что override подхватился:

```bash
docker compose -f docker-compose.yml -f docker-compose.mac-amd64.yml config --quiet
```

### 4.7. Доступы

Те же, что на Windows: Airflow 8080, Superset 8088, MinIO 9001,
StarRocks 8030/9030.

---

## 5. Скрытые условия (обязательно прочитать)

Это не «магия», а реальные prerequisites, без которых сборка/запуск могут
не пройти.

### 5.1. Интернет при первой сборке

Нужны:

- Docker Hub / GHCR — образы;
- PyPI — Python-пакеты;
- Maven Central — Spark-зависимости при первом Spark ETL.

Первый запуск может скачать несколько сотен МБ (Spark Maven-кэш ~300+ МБ).
Без интернета сборка не завершится.

### 5.2. Docker Hub rate limit

При частых пересборках возможен `429 Too Many Requests`. Решение:
подождать, залогиниться в Docker Hub или использовать кэш образов.

### 5.3. Docker Compose v2

Проект использует:

- `depends_on: condition: service_healthy`;
- `condition: service_completed_successfully`;
- современный синтаксис.

`docker-compose` v1 не подходит. Нужен `docker compose` (v2).

### 5.4. WSL2 на Windows

Docker Desktop должен использовать WSL2 backend. Без виртуализации
(`Virtualization` в BIOS, Hyper-V/WSL2) Linux-контейнеры не запустятся.

### 5.5. Память Docker

Docker Desktop по умолчанию может выделить 2 ГБ. Этого мало:
StarRocks + Airflow + Superset + Spark требуют 8+ ГБ. Если контейнер
падает с `Exited (137)` — это OOM.

На Linux Docker Desktop нет: ограничения задаются памятью хоста и cgroup.
Проверьте `docker stats` и `free -h`; при нехватке RAM используйте режимы
`start-airflow` / `start-superset`.

### 5.6. Свободные порты

Если 8080 занят (например, старым Trino/Hive), Airflow не стартует.

Windows:

```powershell
Get-NetTCPConnection -LocalPort 8080 -State Listen
```

Linux:

```bash
ss -ltnp | grep 8080
```

macOS:

```bash
lsof -nP -iTCP:8080 -sTCP:LISTEN
```

### 5.7. `.env`

`docker compose` использует `.env` для подстановки `${...}`. Если файла нет
или значения пустые — часть сервисов не поднимется. `.env` уже есть в
репозитории (учебные значения).

### 5.8. LF для shell-скриптов

Если `.sh` приедет с CRLF, Linux/macOS выдаст:

```
env: 'bash\r': No such file or directory
```

В проекте `.sh` уже LF, `.gitattributes` это закрепляет. Если вы копируете
папку с Windows вручную (не через git), выполните на Linux/macOS:

```bash
find . -name "*.sh" -exec dos2unix {} \;
```

или используйте `git clone`, а не копирование.

### 5.9. Исполняемый бит

Если скрипт не запускается:

```bash
chmod +x scripts/linux/*.sh
```

Или запускайте через `bash`.

### 5.10. Superset `mysqlclient`

`mysqlclient` собирается из исходников. В `superset/Dockerfile` уже есть:

- `default-libmysqlclient-dev`;
- `libssl-dev`;
- `build-essential`;
- `pkg-config`;
- `python3-dev`.

На arm64 это работает, но сборка дольше. Нужен интернет и место на диске.

### 5.11. `mysql-connector-python` на arm64

На arm64 нет native aarch64 wheel для 8.0.33, поэтому pip ставит
pure-Python wheel. Это совместимо, но медленнее. Если `dbt debug` падает,
смотрите логи и при необходимости используйте advanced fallback
`mysql-connector-python==8.4.0` (есть aarch64 wheel), но проверьте
`dbt run/test`.

### 5.12. StarRocks/Spark/Iceberg REST на arm64

Манифесты содержат arm64, но это тяжёлые JVM-сервисы. Если конкретный тег
ведёт себя нестабильно (падает/OOM/ошибки BE), используйте:

```bash
USE_AMD64=1 ./scripts/linux/start-all.sh
```

и включите Rosetta. Это медленнее, но обычно стабильнее для x86-only
сценариев.

### 5.13. Iceberg REST metadata

`apache/iceberg-rest-fixture` хранит каталог в `/tmp` внутри контейнера.
После пересоздания `iceberg-rest` нужно снова выполнить Spark ETL.
Подробно — [`modules/06-spark-iceberg.md`](modules/06-spark-iceberg.md).

### 5.14. Superset results backend

Superset использует Redis (db 4) для SQL Lab/части чартов. Redis должен
быть запущен. В полном стеке он есть; в Superset-only режиме POSIX-скрипт
запускает его сам.

### 5.15. One-shot сервисы

`airflow-init`, `data-init`, `dbt`, `superset-init`, `superset-dashboards`
завершаются с `Exited (0)`. Это успех, а не падение.

### 5.16. Linux: права на bind mounts

Airflow-образ работает под UID `50000` (пользователь `airflow`). На
нативном Linux bind mounts проверяют права, поэтому Airflow worker может
не суметь писать в:

- `./airflow/logs` — логи задач;
- `./project/models/staging` — генератор перезаписывает `stg_*.sql`.

Симптом: `Permission denied` в `generate_and_upload` или Airflow не пишет
логи.

Варианты:

```bash
# ACL (предпочтительно, не меняет владельца). На Ubuntu/Debian:
# sudo apt-get install -y acl
sudo setfacl -R -m u:50000:rwx project airflow/logs
sudo setfacl -R -d -m u:50000:rwx project airflow/logs

# Или локальный учебный вариант (широкие права, только dev)
chmod -R o+rwX project airflow/logs
```

После `data-init`/`dbt` файлы могут быть созданы от root (dbt-образ
запускается от root). Если хост не может их редактировать:

```bash
sudo chown -R "$USER":"$USER" project
```

### 5.17. Linux: SELinux

На Fedora/RHEL/CentOS с SELinux bind mounts могут быть запрещены, даже
если Unix-права верные. Симптом: `Permission denied` при чтении
`/opt/airflow/dags`, `/dbt/project`, `/opt/spark/...`.

Варианты:

```bash
getenforce
sudo chcon -Rt container_file_t /path/to/dbt_sample
```

Либо добавить `:z` к bind-mount volumes в `docker-compose.yml` (только
Linux/SELinux). Не добавляйте `:z` на macOS/Windows без необходимости.

### 5.18. Linux: лимиты для StarRocks

StarRocks BE — тяжёлый JVM/движок. На некоторых Linux-хостах нужны:

```bash
sudo sysctl -w vm.max_map_count=2000000
echo 'vm.max_map_count=2000000' | sudo tee /etc/sysctl.d/99-starrocks.conf
```

В `docker-compose.yml` для `starrocks` уже задан
`ulimits.nofile: 65535`. Если BE всё равно падает с `too many open files`,
проверьте лимиты Docker daemon/host. В Docker Desktop эти лимиты обычно уже
высокие.

### 5.19. Linux: Docker Engine и Compose plugin

На Linux не нужен Docker Desktop. Нужны:

- Docker Engine;
- Compose plugin (`docker compose`);
- пользователь в группе `docker` или корректные права на socket.

Проверка:

```bash
docker version
docker compose version
docker info | grep -i "Total Memory"
```

### 5.20. Volumes

`docker compose down` сохраняет данные. `docker compose down -v` удаляет
StarRocks/MinIO/Superset/Postgres. Не используйте `-v` без необходимости.

---

## 6. Проверка после сборки

> Команды ниже — для Linux/macOS. В PowerShell используйте `curl.exe` или
> `Invoke-WebRequest`; команды `docker ...` работают так же.

```bash
# 1. Статусы
docker compose ps -a

# 2. Health
curl -fsS http://localhost:8080/health
curl -fsS http://localhost:8088/health
curl -fsS http://localhost:8181/v1/config
curl -fsS http://localhost:9000/minio/health/live

# 3. dbt
docker compose logs dbt --tail 100

# 4. StarRocks
docker exec starrocks mysql -h 127.0.0.1 -P 9030 -uroot \
  -e "SELECT COUNT(*) FROM analytics.mart_retail__sales_by_month;"

# 5. Airflow DAG
docker exec airflow_scheduler airflow dags list
docker exec airflow_scheduler airflow dags list-import-errors

# 6. Superset
# открыть http://localhost:8088, admin/admin, оба дашборда
```

Ожидаемо:

- long-running сервисы `Up`;
- `dbt` — `PASS=39`, `PASS=19`;
- `mart_retail__sales_by_month` = 13;
- Airflow DAG виден без ошибок;
- Superset показывает `Supply Chain Overview` и `Retail Overview`.

Полный чек-лист — [`modules/10-checks-and-tests.md`](modules/10-checks-and-tests.md).

---

## 7. Troubleshooting по платформам

### 7.1. Windows

| Симптом | Причина | Решение |
|---|---|---|
| `docker` не найден | Docker Desktop не установлен/не запущен | установить/запустить |
| `scripts\windows\start-all.ps1 cannot be loaded` | ExecutionPolicy | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| `wsl` ошибка | WSL2 не установлен | `wsl --install`, перезагрузка |
| `Exited 137` | мало RAM | `.wslconfig` memory=8GB+, перезапуск |
| `.sh` падает с `\r` | CRLF | Git clone с `.gitattributes` / `dos2unix` |
| Порт занят | старый контейнер | `docker ps -a`, `docker rm -f` |

### 7.2. Linux

| Симптом | Причина | Решение |
|---|---|---|
| `Cannot connect to the Docker daemon` | Docker не запущен/нет прав | `sudo systemctl start docker`; `sudo usermod -aG docker "$USER"` + re-login |
| `permission denied /var/run/docker.sock` | пользователь не в группе docker | добавить в группу и перелогиниться |
| `docker compose: command not found` | нет Compose plugin | установить `docker-compose-plugin` / Docker Engine |
| `Permission denied` на `airflow/logs` или `project` | Airflow UID 50000 не может писать в bind mount | `sudo setfacl -R -m u:50000:rwx project airflow/logs` или `chmod -R o+rwX ...` |
| `Permission denied` после `data-init` | файлы созданы root | `sudo chown -R "$USER":"$USER" project` |
| `StarRocks BE mmap/too many open files` | низкие host limits | `sudo sysctl -w vm.max_map_count=2000000`; увеличить `nofile` |
| SELinux denies bind mount | SELinux enforcing | добавить `:z` к volume или `sudo chcon -Rt container_file_t <project>` |
| `port is already allocated` | порт занят | `ss -ltnp | grep 8080` |
| `Exited 137` | OOM | увеличить RAM / ограничить сервисы |

### 7.3. macOS

| Симптом | Причина | Решение |
|---|---|---|
| `Cannot connect to the Docker daemon` | Docker Desktop не запущен | запустить Docker Desktop |
| `no matching manifest for linux/arm64` | тег без arm64 | `USE_AMD64=1` |
| `exec format error` | amd64-образ без Rosetta | включить Rosetta / fallback |
| `Permission denied` на `airflow/logs` | bind mount/права | `chmod -R u+rwX airflow/logs`; не iCloud |
| `mysqlclient` build failed | нет зависимостей/сети | пересобрать; проверить интернет |
| `dbt` connector error | pure wheel/версия | `dbt debug`, advanced fallback 8.4.0 |
| `Exited 137` | мало RAM | Docker Desktop → Resources → 8GB+ |
| `port is already allocated` | порт занят | `lsof -nP -iTCP:8080 -sTCP:LISTEN` |
| `Operation not permitted` | файловая папка | перенести проект в `~/Projects` |
| `no space left on device` | мало диска Docker | увеличить Disk image size |

---

## 8. Матрица скриптов

| Задача | Windows | Linux/macOS |
|---|---|---|
| Полный стек | `.\scripts\windows\start-all.ps1` | `./scripts/linux/start-all.sh` |
| Airflow без Superset | `.\scripts\windows\start-airflow.ps1` | `./scripts/linux/start-airflow.sh` |
| Superset без Airflow | `.\scripts\windows\start-superset.ps1` | `./scripts/linux/start-superset.sh` |
| Остановить | `.\scripts\windows\stop.ps1` | `./scripts/linux/stop.sh` |
| Полный сброс | `docker compose down -v` | `docker compose down -v` |
| Fallback amd64 | — | `USE_AMD64=1 ./scripts/linux/start-all.sh` |

---

## 9. Что не требуется

- Xcode / Command Line Tools на Mac — сборка идёт в Linux-контейнерах.
- Java/Spark/dbt на хосте.
- Node.js.
- Python на хосте.
- `jq`, `make`, `dos2unix` (кроме ручной нормализации скопированных `.sh`).
- PowerShell на Linux/macOS.
- Docker Desktop на Linux (достаточно Docker Engine + Compose plugin).

Требуются только Docker (Desktop или Engine), Git (или архив) и свободные
порты.

---

## 10. Что осталось проверить на реальном Linux/Mac

Статически проверено:

- arm64-манифесты всех образов;
- arm64 wheels для dbt-extractor;
- pure-Python wheel для mysql-connector 8.0.33;
- LF для всех `.sh`;
- `.gitattributes`;
- compose config с Mac-override;
- синтаксис Windows PowerShell-скриптов;
- синтаксис Linux bash-скриптов (`bash -n`);
- LF и структура скриптов.

На первом запуске на Linux/Mac проверьте:

1. `docker compose up -d --build` доходит до конца.
2. `dbt` logs: `PASS=39`, `PASS=19`.
3. Airflow DAG run success.
4. Superset дашборды открываются.
5. Spark ETL и StarRocks external catalog.
6. На Linux — что Airflow worker может писать в `project/` и
   `airflow/logs/` (см. права ниже).

Если что-то падает — в отчёте/issue укажите:

- ОС, архитектуру (amd64/arm64), для Mac — Intel/Apple Silicon;
- версию Docker/Compose;
- `id -u` (Linux) и `docker compose ps -a`;
- `docker compose logs <service>`;
- использовался ли `USE_AMD64=1`;
- вывод `getenforce` (если Linux/SELinux).

---

## 11. Связанные документы

- [`RUNBOOK.md`](RUNBOOK.md) — эксплуатация и проверки.
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — устройство проекта.
- [`modules/01-infrastructure.md`](modules/01-infrastructure.md) — Compose,
  порты, volumes.
- [`modules/09-scripts-and-legacy.md`](modules/09-scripts-and-legacy.md) —
  start-скрипты и legacy-предупреждения.
