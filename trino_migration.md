# Trino migration — полная миграция StarRocks → Trino

**Дата:** 2026-11-13  
**Статус:** завершена, StarRocks удалён.

---

## 1. Итог

Проект полностью переведён на **Trino + Iceberg**:

- StarRocks удалён из compose, образов, dbt, Superset, Airflow и docs;
- все 15 supply + 11 retail raw-таблиц загружены в Iceberg через Spark;
- dbt-trino собрал **26 staging views + 11 marts**;
- `dbt run` — **PASS=37**, `dbt test` — **PASS=19**;
- Trino работает на порту **8081**, DBeaver проверен;
- Superset переведён на `trino[sqlalchemy]`;
- Airflow DAG переписан на Spark + dbt-trino.

---

## 2. Что удалено

- сервис `starrocks`, порты 8030/9030/8040, volume `starrocks_data`;
- `dbt-starrocks`, `pymysql`, `mysql-connector-python`;
- `load_s3_to_starrocks.py`, `load_retail_to_starrocks.py`;
- `spark/init-starrocks.sql`;
- StarRocks external catalog и все MOEX-модели (удалены ранее);
- Superset-драйвер `starrocks`, `add_starrocks_db.py`;
- StarRocks-задачи из Airflow DAG.

---

## 3. Что добавлено

| Компонент | Файл |
|---|---|
| Trino | `trino/etc/config.properties`, `node.properties`, `jvm.config` |
| Iceberg catalog | `trino/etc/catalog/iceberg.properties` |
| Trino service | `docker-compose.yml` (`8081:8080`) |
| Persistent catalog | volume `iceberg_catalog_data:/tmp` |
| Spark full ETL | `spark/jobs/etl_all_to_iceberg.py` |
| spark-etl service | one-shot `spark-etl` |
| dbt-trino | `dbt/Dockerfile`, `dbt/profiles/profiles.yml` |
| Airflow Spark | `pyspark` + Java 17 в `airflow/Dockerfile` |
| Superset Trino | `trino[sqlalchemy]`, `add_trino_db.py` |

---

## 4. Архитектура

```
generate_*.py
  -> MinIO CSV
  -> Spark (spark-etl / Airflow worker)
  -> Iceberg tables (S3)
  -> Iceberg REST catalog
  -> Trino
  -> dbt-trino
  -> Superset / DBeaver
```

---

## 5. Данные

| Таблица | Строк |
|---|---:|
| `raw_suppliers` | 100 000 |
| `raw_supply_orders` | 100 000 |
| `raw_retail_orders` | 200 000 |
| `raw_retail_order_items` | 379 702 |
| `raw_retail_customers` | 50 000 |
| `mart_supplier_performance` | 100 000 |
| `mart_warehouse_activity` | 100 000 |
| `mart_retail__customer_ltv` | 50 000 |
| `mart_retail__sales_by_month` | 13 |

Всего: 26 raw, 26 staging views, 11 marts.

---

## 6. DBeaver

```text
Driver:   Trino
Host:     localhost
Port:     8081
User:     trino
Password: (пусто)
Catalog:  iceberg
Schema:   analytics
JDBC:     jdbc:trino://localhost:8081/iceberg/analytics
```

Проверка:

```sql
SHOW TABLES FROM iceberg.analytics;
SELECT COUNT(*) FROM iceberg.analytics.mart_retail__sales_by_month;
SELECT COUNT(*) FROM iceberg.analytics.mart_supplier_performance;
```

---

## 7. Число шагов

**32 шага:**

| № | Шаг |
|---:|---|
| 1 | Аудит StarRocks/MOEX-следов |
| 2 | Удаление MOEX-файлов и моделей |
| 3 | Удаление MOEX-таблиц/views из StarRocks |
| 4 | Удаление MOEX из MinIO |
| 5 | Проверка arm64-совместимости Trino |
| 6 | Конфиги Trino (config/node/jvm) |
| 7 | Iceberg REST + S3 в Trino |
| 8 | Trino service в compose |
| 9 | dbt-trino в dbt-образе |
| 10 | Тестовый Trino dbt-проект |
| 11 | Spark job на retail-срез |
| 12 | Запуск Trino/Iceberg/MinIO |
| 13 | Проверка трино-каталога |
| 14 | Загрузка retail-среза в Iceberg |
| 15 | dbt-trino test slice PASS |
| 16 | Полное удаление MOEX |
| 17 | Spark full ETL job (15+11) |
| 18 | `spark-etl` one-shot service |
| 19 | Persistent volume `iceberg_catalog_data` |
| 20 | Перевод основного профиля dbt на Trino |
| 21 | Конвертация 11 mart-конфигов |
| 22 | Удаление StarRocks-загрузчиков и SQL |
| 23 | Переписывание DAG на Spark + dbt-trino |
| 24 | Переписывание Airflow-образа |
| 25 | Перевод Superset на Trino |
| 26 | Загрузка 26 raw-таблиц в Iceberg |
| 27 | `dbt run` 37 моделей |
| 28 | Исправление диалектных ошибок |
| 29 | `dbt test` 19 тестов |
| 30 | Удаление StarRocks service/volume |
| 31 | Проверка Trino/DBeaver |
| 32 | Переписывание documentation под Trino |

---

## 8. Ошибки и исправления

**11 ошибок/препятствий**, все исправлены:

| № | Ошибка | Исправление |
|---:|---|---|
| 1 | Docker-контейнеры не запущены | `docker compose up -d` |
| 2 | `DROP TABLE` для `stg_moex_*` | `DROP VIEW` |
| 3 | MinIO недоступен при удалении MOEX | запустили MinIO, повторили `mc rm` |
| 4 | Iceberg REST потерял metadata | persistent volume + повторный Spark ETL |
| 5 | `dbt --profiles-dir ... run` | опции после `run` |
| 6 | Retail-генератор завис (O(N²)) | выбор по `randrange` |
| 7 | Spark OOM на 100k suppliers | memory 2g → 4g |
| 8 | `datediff` не найден в Trino | `date_diff('day', ...)` |
| 9 | `r.transport_mode` при `USING` | `FULL OUTER JOIN ... ON` |
| 10 | StarRocks orphan container | `docker rm -f starrocks` |
| 11 | StarRocks volume остался | `docker volume rm dbt_sample_starrocks_data` |

Прямо к Trino-миграции относятся ошибки №4, №5, №8, №9; остальные —
инфраструктура/данные.

---

## 9. Проверка

```powershell
docker compose config --quiet
docker exec trino trino --execute "SHOW CATALOGS"
docker exec trino trino --execute "SHOW TABLES FROM iceberg.analytics"
docker compose run --rm --no-deps --entrypoint dbt dbt test `
  --profiles-dir /dbt/profiles --project-dir /dbt/project
```

Ожидаемо: `PASS=19`, Trino видит 26+26+11 объектов.

---

## 10. Документация

Активная документация переписана под Trino:

- `README.md`;
- `docs/README.md`, `ARCHITECTURE.md`, `RUNBOOK.md`, `BUILD.md`,
  `DATA_MODEL.md`, `DEVELOPMENT_GUIDE.md`, `ROADMAP.md`;
- модули `01`–`10` (StarRocks-модуль заменён на `05-trino.md`);
- `airflow/README.md`, `dbt/README.md`, `spark/README.md`,
  `superset/README.md`, `scripts/README.md`.

---

## 11. Ограничения

- `iceberg-rest-fixture` — учебный; для production нужен JDBC/Nessie.
- Spark ETL не incremental.
- Airflow Spark — `local[2]`, не кластер.
- Партиционирование Iceberg пока не настроено.

---

## 12. Итоговый статус

**READY WITH LIMITATIONS.**

Проект полностью работает на Trino + Iceberg, StarRocks удалён,
все 37 моделей и 19 тестов проходят.
