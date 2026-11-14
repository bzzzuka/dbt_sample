# Модуль 03 — dbt-trino

**Файлы:**

- `dbt/Dockerfile`
- `dbt/profiles/profiles.yml`
- `dbt/scripts/run_dbt.sh`
- `project/dbt_project.yml`
- `project/models/staging/**`
- `project/models/marts/**`

---

## 1. Роль

dbt строит staging views и marts-таблицы в Iceberg через Trino:

```
Iceberg raw_* -> dbt-trino staging views -> dbt-trino marts tables
```

StarRocks-адаптер удалён. Используется `dbt-trino==1.6.2` и `dbt-core==1.6.2`.

---

## 2. Профиль

`dbt/profiles/profiles.yml`:

```yaml
default:
  target: dev
  outputs:
    dev:
      type: trino
      method: none
      user: "{{ env_var('TRINO_USER', 'trino') }}"
      host: "{{ env_var('TRINO_HOST', 'trino') }}"
      port: "{{ env_var('TRINO_PORT', '8080') | int }}"
      database: "{{ env_var('TRINO_CATALOG', 'iceberg') }}"
      schema: "{{ env_var('TRINO_SCHEMA', 'analytics') }}"
      threads: 4
```

---

## 3. Модели

- staging — 26 views;
- marts — 11 tables с `{{ config(materialized='table', format='PARQUET') }}`;
- всего **37 моделей**, **19 тестов**, **26 sources**.

Никаких `engine`, `keys`, `distributed_by`, `buckets`, `properties` —
это StarRocks-конфиги, они удалены.

---

## 4. Trino-диалект

Вместо StarRocks-функций:

| StarRocks | Trino |
|---|---|
| `DATEDIFF(a, b)` | `date_diff('day', b, a)` |
| `DATE_FORMAT(x, '%Y-%m-01')` | `date_trunc('month', x)` |
| `USING (col)` + `r.col` | `JOIN ... ON r.col = s.col` |
| `FILES()` | Spark CSV → Iceberg |

---

## 5. Запуск

```powershell
docker compose run --rm --no-deps --entrypoint dbt dbt run `
  --profiles-dir /dbt/profiles --project-dir /dbt/project

docker compose run --rm --no-deps --entrypoint dbt dbt test `
  --profiles-dir /dbt/profiles --project-dir /dbt/project
```

Селекторы:

```powershell
docker compose run --rm --no-deps --entrypoint dbt dbt run `
  --profiles-dir /dbt/profiles --project-dir /dbt/project `
  --select mart_supplier_performance mart_retail__sales_by_month
```

Ожидаемо: `PASS=37`, тесты `PASS=19`.

---

## 6. Генерируемые staging

`generate_and_upload.py` перезаписывает 15 supply `stg_*.sql` и
`sources.yml` при `data-init`. Retail staging не перезаписывается.

---

## 7. Проверка

```sql
SHOW TABLES FROM iceberg.analytics;
DESCRIBE iceberg.analytics.mart_supplier_performance;
SELECT * FROM iceberg.analytics.mart_retail__sales_by_month LIMIT 10;
```

---

## 8. Частые ошибки

| Ошибка | Решение |
|---|---|
| `FUNCTION_NOT_FOUND` | заменить StarRocks-функцию на Trino |
| `COLUMN_NOT_FOUND` | `USING` → `ON` |
| `No such option --profiles-dir` | опции после `run`, не перед |
| Trino connection refused | Trino не поднят или нет `trino[sqlalchemy]`/dbt-trino |
| raw-таблиц нет | `docker compose run --rm --no-deps spark-etl` |

---

## 9. Связанные документы

- [`05-trino.md`](05-trino.md)
- [`06-spark-iceberg.md`](06-spark-iceberg.md)
- [`../DEVELOPMENT_GUIDE.md`](../DEVELOPMENT_GUIDE.md)
