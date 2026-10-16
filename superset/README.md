# superset — BI и дашборды

Модуль отвечает за **визуализацию данных** из StarRocks.
Superset читает таблицы `mart_*` (и через external catalog — Iceberg)
и строит интерактивные дашборды для бизнес-пользователей.

Здесь только **инфраструктура** — сам дашборд «Supply Chain Overview»
создаётся скриптом при первом запуске.

---

## Структура

    superset/
    ├── README.md                        # Этот файл
    ├── Dockerfile                       # Образ Superset + драйвер StarRocks
    ├── requirements-local.txt           # Список pip-пакетов
    └── init/
        ├── init-db.sh                   # Entrypoint для superset-init
        ├── add_starrocks_db.py          # Добавляет подключение к StarRocks
        └── create_dashboard.py          # Создаёт дашборд через REST API

---

## Зачем это нужно

Модуль решает три задачи:

1. **Сборка окружения** — образ Superset с драйвером StarRocks.
2. **Инициализация** — миграции БД метаданных, создание админа,
   подключение к StarRocks.
3. **Дашборды** — программное создание чартов и дашборда «Supply Chain Overview».

Что даёт Superset:

- **SQL Lab** — интерактивный SQL-редактор к StarRocks.
- **Charts** — более 50 типов визуализаций (bar, line, pie, table, ...).
- **Dashboards** — компоновка чартов на одном экране.
- **Filters** — интерактивные фильтры по измерениям.
- **Alerts & Reports** — рассылка PDF-отчётов по расписанию.

---

## Архитектура

    +----------------+
    |   Superset     |
    |   (webserver)  |
    +--------+-------+
             |
             v
    +----------------+     +-------------+
    |  StarRocks     |<----|  SQL Lab    |
    |  (MySQL:9030)  |     |  Charts     |
    +--------+-------+     |  Dashboards |
             |             +-------------+
             v
    +----------------+
    |  mart_* tables |
    |  (StarRocks)   |
    +----------------+

Дополнительно — **Superset Worker** обрабатывает асинхронные задачи:
- длинные SQL-запросы (`allow_run_async=True`),
- scheduled reports (PDF/PNG),
- alerts.

---

## Dockerfile

**Базовый образ:** apache/superset:4.1.2

**Что устанавливается:**

| Пакет                     | Зачем                                          |
|---------------------------|------------------------------------------------|
| default-libmysqlclient-dev| Системные библиотеки для сборки mysqlclient    |
| build-essential           | gcc для компиляции C-расширений                |
| python3-dev, python3-pip  | Python-заголовки и pip                         |
| python3-venv              | venv (образ Superset использует venv)          |
| default-mysql-client      | CLI-клиент `mysql` (для init-db.sh)            |
| mysqlclient               | Python-драйвер MySQL/MariaDB                   |
| starrocks==1.0.6          | SQLAlchemy-драйвер StarRocks                   |

**Почему именно такие версии:**

| Пакет       | Версия | Причина                                                       |
|-------------|--------|---------------------------------------------------------------|
| Superset    | 4.1.2  | Стабильная, с поддержкой SQLAlchemy 1.4                       |
| starrocks   | 1.0.6  | Последняя, совместимая с SQLAlchemy 1.4 (2.0 — конфликт)      |
| mysqlclient | любая  | Нужен для CLIdriver                                            |

**Критичные моменты:**

1. **`ensurepip` НЕ используется.** В образе `apache/superset:4.1.2` venv
   `/app/.venv` не содержит pip. Установка pip через `ensurepip` падает
   с `command not found`. Решение — ставить пакеты через **системный pip**
   (он пишет в `/app/.venv` благодаря PATH).

2. **Зеркало PyPI.** `pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple` —
   скорость из РФ в 10–50× выше.

3. **`default-mysql-client`** — обязателен. Без него `init-db.sh` зависает
   на `mysql -h starrocks -e "SELECT 1"`, потому что команда не найдена.

**Переменные окружения:**

    PATH=/app/.venv/bin:$PATH
    SUPERSET_HOME=/app/superset_home

**Что копируется:**

- requirements-local.txt → /app/docker/requirements-local.txt
- init/ → /app/init/

**CMD:** `bash` (переопределяется в docker-compose).

---

## requirements-local.txt

**Назначение:** список pip-пакетов для Superset.

**Содержимое:**

    starrocks==1.0.6
    mysqlclient

**Почему отдельным файлом:**

- Dockerfile копирует его и делает `pip install -r`.
- Легко менять зависимости без правки Dockerfile.
- Явно видно, что добавлено в Superset сверх базового образа.

**Что делает `starrocks`:**

Это SQLAlchemy-диалект. Он говорит Superset, как:
- подключаться к StarRocks (`starrocks://user:pass@host:port/catalog.schema`),
- генерировать SQL для StarRocks,
- читать метаданные (список таблиц, схемы).

Без него подключение к StarRocks невозможно — Superset не знает такой БД.

---

## init/init-db.sh

**Entrypoint сервиса `superset-init`.**

**Полный скрипт:**

    #!/usr/bin/env bash
    set -e

    echo "=== Superset init ==="

    echo "Ожидание StarRocks (${STARROCKS_HOST}:${STARROCKS_PORT})..."
    until mysql -h "${STARROCKS_HOST}" -P "${STARROCKS_PORT}" -u"${STARROCKS_USER}" \
            -e "SELECT 1" >/dev/null 2>&1; do
        sleep 3
    done
    echo "StarRocks доступен."

    echo ">>> Миграции Superset"
    superset db upgrade

    echo ">>> Создание админа (admin/admin)"
    superset fab create-admin \
        --username admin \
        --firstname Admin \
        --lastname User \
        --email admin@example.com \
        --password admin || true

    echo ">>> Инициализация ролей и прав"
    superset init

    echo ">>> Добавление подключения к StarRocks"
    python /app/init/add_starrocks_db.py

    echo "=== Superset init завершён ==="

**Пошагово:**

| Шаг                             | Что делает                                                        |
|---------------------------------|-------------------------------------------------------------------|
| `set -e`                        | Останавливаться при первой ошибке                                  |
| `until mysql ... SELECT 1`      | Ждать StarRocks (проверка каждые 3 сек)                            |
| `superset db upgrade`           | Миграции БД метаданных Superset (SQLite в volume `superset_home`)  |
| `superset fab create-admin`     | Создать админа `admin/admin`. `\|\| true` — если уже есть, не падать |
| `superset init`                 | Синхронизировать роли, права, создать дефолтные объекты            |
| `python add_starrocks_db.py`    | Добавить подключение к StarRocks в метаданные                      |

**Почему отдельный init-контейнер:**

1. **Миграции должны выполняться ОДИН раз.** Если 3+ воркера запустятся
   одновременно — БД метаданных сломается (`race condition`).
2. **Порядок:** миграции → админ → права → подключения. Только после этого
   можно запускать `superset` (webserver).
3. **Идемпотентность:** повторный запуск безопасен — все команды умеют
   проверять существование.

**Что делает `until mysql ... SELECT 1`:**

StarRocks не сразу готов принимать запросы даже после старта контейнера.
Цикл проверяет подключение каждые 3 секунды до первого успеха.

Если **`default-mysql-client` не установлен** — команда `mysql` не найдётся,
цикл будет висеть бесконечно (в логах — `Waiting for StarRocks...`).
Именно это и была одна из первых ошибок.

---

## init/add_starrocks_db.py

**Назначение:** программно добавляет подключение к StarRocks в метаданные Superset.

**Полный скрипт:**

    import os
    import sys

    sys.path.append("/app")
    from superset import create_app
    from superset import db

    app = create_app()

    with app.app_context():
        from superset.models.core import Database

        host = os.getenv("STARROCKS_HOST", "starrocks")
        port = os.getenv("STARROCKS_PORT", "9030")
        user = os.getenv("STARROCKS_USER", "root")
        password = os.getenv("STARROCKS_PASSWORD", "")
        catalog = os.getenv("STARROCKS_CATALOG", "default_catalog")
        schema = os.getenv("STARROCKS_SCHEMA", "analytics")

        uri = f"starrocks://{user}:{password}@{host}:{port}/{catalog}.{schema}?charset=utf8"

        existing = db.session.query(Database).filter_by(database_name="StarRocks Analytics").first()
        if existing:
            print(f"Подключение уже существует: {existing.database_name}")
        else:
            new_db = Database(
                database_name="StarRocks Analytics",
                sqlalchemy_uri=uri,
                expose_in_sqllab=True,
                allow_run_async=True,
            )
            db.session.add(new_db)
            db.session.commit()
            print(f"Создано подключение: {uri}")

**Что делает:**

1. Создаёт Flask-app (Superset).
2. Открывает `app_context()` — обязательно для работы с моделями БД.
3. **Внутри контекста** импортирует `Database` — модель подключения.
4. Проверяет, есть ли уже подключение `StarRocks Analytics`.
5. Если нет — создаёт его с URI и параметрами.
6. Коммитит транзакцию в метаданные.

**Критичные тонкости:**

1. **Импорт `Database` — ВНУТРИ `app_context()`.**
   Если импортировать снаружи, Flask упадёт с `RuntimeError: Working outside
   of application context`. Причина: модель обращается к `app.config` при
   импорте.

2. **`from superset import db`, а не `from superset.app import DB`.**
   В Superset 4.1.2 объект SQLAlchemy доступен как `superset.db`.
   Старый путь `superset.app.DB` — не работает.

3. **URI формат:**