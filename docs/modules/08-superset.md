# Модуль 08 — Superset

**Файлы:**

- `superset/Dockerfile`
- `superset/requirements-local.txt`
- `superset/init/init-db.sh`
- `superset/init/add_trino_db.py`
- `superset/init/create_all_dashboards.py`
- `superset/superset_config.py`

---

## 1. Сервисы

| Сервис | Роль |
|---|---|
| `superset` | UI на 8088 |
| `superset-init` | миграции, admin, Trino connection |
| `superset-worker` | Celery worker |
| `superset-dashboards` | дашборды (one-shot) |

---

## 2. Подключение

`superset/init/add_trino_db.py` создаёт connection:

```
trino://trino@trino:8080/iceberg/analytics
```

Имя: `Trino Iceberg`.

StarRocks-драйвер удалён; в requirements:

```
trino[sqlalchemy]==0.340.0
```

---

## 3. init

`init-db.sh`:

1. ждёт `http://trino:8080/v1/info`;
2. `superset db upgrade`;
3. admin/admin;
4. `superset init`;
5. `python /app/init/add_trino_db.py`.

---

## 4. Дашборды

`create_all_dashboards.py`:

- 11 datasets;
- 16 charts;
- 2 dashboards: `Supply Chain Overview`, `Retail Overview`.

Идемпотентно: `find_or_create` по имени.

Материализация — Trino/Iceberg marts, не raw.

---

## 5. Проверка

- http://localhost:8088 → admin/admin;
- SQL Lab → `Trino Iceberg` → `analytics`;
- открыть оба дашборда.

```sql
SELECT COUNT(*) FROM analytics.mart_supplier_performance;
SELECT COUNT(*) FROM analytics.mart_retail__sales_by_month;
```

---

## 6. Ограничения

- Trino-драйвер требует `trino[sqlalchemy]`;
- results backend — Redis db 4;
- metadata Superset — SQLite;
- `iceberg-rest-fixture` — учебный.

---

## 7. Связанные документы

- [`05-trino.md`](05-trino.md)
- [`../RUNBOOK.md`](../RUNBOOK.md)
