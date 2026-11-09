# Модуль 08 — Superset (BI)

**Файлы модуля:**

- `superset/Dockerfile`
- `superset/requirements-local.txt`
- `superset/init/init-db.sh`
- `superset/init/add_starrocks_db.py`
- `superset/init/create_all_dashboards.py` — актуальный скрипт дашбордов
- `superset/init/create_dashboard.py` — legacy-скрипт только Supply Chain
- `superset/superset_config.py`
- сервисы `superset`, `superset-init`, `superset-worker`,
  `superset-dashboards` в `docker-compose.yml`

---

## 1. Роль модуля

Superset — BI-слой. Он подключается к StarRocks и строит дашборды поверх
готовых витрин `analytics.mart_*`.

Важно: дашборды строятся **не** поверх `raw_*` или `stg_*`, а поверх
`mart_*`. Это гарантирует, что в графиках уже посчитаны агрегаты.

---

## 2. Сервисы

| Сервис | Роль |
|---|---|
| `superset` | webserver / UI на 8088 |
| `superset-init` | one-shot: миграции, admin, connection StarRocks |
| `superset-worker` | Celery worker для асинхронных задач |
| `superset-dashboards` | one-shot: создание датасетов, чартов, дашбордов |

`superset` зависит от `superset-init`, `starrocks` и healthy `redis`.  
`superset-dashboards` зависит от healthy `superset` и `redis`.

---

## 3. Образ Superset

Файл: `superset/Dockerfile`.

База: `apache/superset:4.1.2`.

Устанавливается:

- `starrocks==1.0.6` — SQLAlchemy-диалект;
- `mysqlclient` — драйвер;
- системные зависимости для сборки (`default-libmysqlclient-dev`,
  `build-essential`, `pkg-config`, `python3-dev`);
- `default-mysql-client` — для `init-db.sh` (ожидание StarRocks).

`requirements-local.txt`:

```
starrocks==1.0.6
mysqlclient
```

---

## 4. Superset init

Файл: `superset/init/init-db.sh`.

Шаги:

1. ждёт StarRocks через `mysql -h starrocks -P 9030 -e "SELECT 1"`;
2. `superset db upgrade`;
3. `superset fab create-admin --username admin --password admin ...`;
4. `superset init`;
5. `python /app/init/add_starrocks_db.py`.

После этого в Superset есть:

- admin/admin;
- подключение `StarRocks Analytics`.

### 4.1. Подключение к StarRocks

Файл: `superset/init/add_starrocks_db.py`.

URI:

```
starrocks://root:@starrocks:9030/default_catalog.analytics?charset=utf8
```

`expose_in_sqllab=True`, `allow_run_async=True`.

Если подключение уже существует, скрипт не создаёт дубликат.

---

## 5. Results backend

Файл: `superset/superset_config.py`.

```python
RESULTS_BACKEND = RedisCache(
    host="redis",
    port=6379,
    db=4,
    key_prefix="superset_results_",
)
```

Зачем: Superset 4.1.2 требует results backend для SQL Lab и части запросов
чартов. Без него ошибка:

```
Results backend is not configured.
```

Redis уже есть в compose (используется Airflow), но Superset использует
отдельную БД 4, чтобы не пересекаться с Celery (0/2/3).

Файл монтируется в `superset`, `superset-init`, `superset-worker`:

```yaml
- ./superset/superset_config.py:/app/pythonpath/superset_config.py:ro
```

и задаётся:

```yaml
- SUPERSET_CONFIG_PATH=/app/pythonpath/superset_config.py
```

---

## 6. Дашборды

### 6.1. Активный скрипт

Файл: `superset/init/create_all_dashboards.py`.

Это one-shot, который выполняется сервисом `superset-dashboards`:

```yaml
command: ["python", "/app/init/create_all_dashboards.py"]
```

Что делает:

1. логинится в Superset API (`admin/admin`);
2. получает CSRF token;
3. находит/создаёт 11 датасетов;
4. находит/создаёт 16 чартов;
5. находит/создаёт 2 дашборда;
6. привязывает чарты к дашбордам;
7. задаёт `position_json` и `json_metadata`;
8. проверяет SQL Lab.

### 6.2. Идемпотентность

Скрипт использует `find_or_create` по имени:

- dataset — по `table_name` и `schema`;
- chart — по `slice_name`;
- dashboard — по `dashboard_title`.

Повторный запуск обновляет существующие объекты, а не создаёт дубликаты.
Это важно, потому что `docker compose up` запускает сервис каждый раз.

### 6.3. Датасеты

Supply chain (6):

```
mart_supplier_performance
mart_supply_by_category
mart_delivery_kpi
mart_warehouse_activity
mart_payment_summary
mart_transport_analysis
```

Retail (5):

```
mart_retail__sales_by_month
mart_retail__top_products
mart_retail__customer_ltv
mart_retail__returns_rate
mart_retail__sales_by_category
```

### 6.4. Дашборд `Supply Chain Overview`

8 чартов:

1. SC: Total Purchase Amount — KPI;
2. SC: Total Orders — KPI;
3. SC: Top-10 Suppliers by Turnover — bar;
4. SC: Revenue by Category — pie;
5. SC: Payments vs Invoices by Month — line;
6. SC: Delivery KPI — table;
7. SC: Top-10 Warehouses by Movements — bar;
8. SC: Delivery Cost by Transport Mode — bar.

### 6.5. Дашборд `Retail Overview`

8 чартов:

1. RT: Total Revenue — KPI;
2. RT: Total Orders — KPI;
3. RT: Avg Order Value — KPI;
4. RT: Revenue by Month — line;
5. RT: Top Products by Revenue — bar;
6. RT: Revenue by Category — pie;
7. RT: Top Customers by LTV — table;
8. RT: Returns Rate by Month — line.

---

## 7. Legacy-скрипт

Файл: `superset/init/create_dashboard.py`.

Это старый скрипт, который создаёт только `Supply Chain Overview` и не
идемпотентен по чартам/дашборду. Он **не используется** в compose.

Актуальный путь — `create_all_dashboards.py` и сервис
`superset-dashboards`. Не запускайте legacy-скрипт, если не хотите
дубликаты.

---

## 8. Как проверять

### 8.1. UI

1. http://localhost:8088
2. `admin/admin`
3. Открыть `Supply Chain Overview` и `Retail Overview`.

### 8.2. API

```powershell
$login = Invoke-RestMethod -Method Post `
  -Uri http://localhost:8088/api/v1/security/login `
  -ContentType 'application/json' `
  -Body '{"username":"admin","password":"admin","provider":"db","refresh":true}'

$h = @{ Authorization = "Bearer $($login.access_token)" }

Invoke-RestMethod -Uri http://localhost:8088/api/v1/dashboard/ -Headers $h |
  Select-Object -ExpandProperty result |
  Select-Object id, dashboard_title, published

Invoke-RestMethod -Uri http://localhost:8088/api/v1/chart/ -Headers $h |
  Select-Object -ExpandProperty result |
  Select-Object id, slice_name, viz_type
```

Ожидаемо: 2 дашборда, 16 чартов.

### 8.3. Логи

```powershell
docker compose logs --tail=100 superset
docker compose logs --tail=100 superset-init
docker compose logs --tail=100 superset-dashboards
docker compose logs --tail=100 superset-worker
```

### 8.4. SQL Lab

В UI: SQL Lab → database `StarRocks Analytics` → schema `analytics`.

```sql
SELECT COUNT(*) FROM mart_retail__sales_by_month;
SELECT COUNT(*) FROM mart_supplier_performance;
```

Если SQL Lab выдаёт `Results backend is not configured` — проверьте
`superset_config.py` и Redis.

---

## 9. Как изменить дашборд

1. Отредактируйте `superset/init/create_all_dashboards.py`.
2. Пересоздайте one-shot:

```powershell
docker compose up -d --force-recreate superset-dashboards
```

3. Проверьте логи и UI.

Не редактируйте чарты только в UI, если хотите, чтобы изменения
воспроизводились: скрипт перезапишет их при следующем запуске.

---

## 10. Ограничения

- Superset metadata хранится в SQLite volume `superset_home`; это ок для
  локального проекта, но не для production.
- Results backend — Redis; без Redis SQL Lab/часть чартов не работают.
- `create_all_dashboards.py` использует REST API Superset 4.1.2; при
  обновлении Superset возможны изменения схемы API.
- Dashboard `position_json` собирается скриптом; ручная раскладка в UI
  может быть перезаписана.
- Admin/admin — учебные credentials.

---

## 11. Частые ошибки

| Ошибка | Причина | Решение |
|---|---|---|
| `Results backend is not configured` | Redis не настроен | `superset_config.py`, Redis |
| Superset не стартует | `superset-init` упал | логи `superset-init` |
| Дашборд пустой | нет `position_json`/charts | перезапустить `superset-dashboards` |
| Чарт не отдаёт данные | dataset/connection | проверить SQL Lab |
| `starrocks` dialect error | неверный URI/драйвер | `starrocks==1.0.6`, `mysqlclient` |
| Дубликаты чартов | запускали legacy `create_dashboard.py` | удалить дубликаты вручную, использовать `create_all_dashboards.py` |
| `superset-worker` unhealthy | Redis/Celery | логи worker, проверить Redis |
| 8088 занят | другой процесс | освободить порт |

---

## 12. Связанные документы

- [`05-starrocks.md`](05-starrocks.md)
- [`../RUNBOOK.md`](../RUNBOOK.md)
- [`../DEVELOPMENT_GUIDE.md`](../DEVELOPMENT_GUIDE.md)
- [`09-scripts-and-legacy.md`](09-scripts-and-legacy.md)
