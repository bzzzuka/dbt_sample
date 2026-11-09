# DEVELOPMENT GUIDE — как развивать проект

**Актуально на:** 2026-11-09  
**Для кого:** инженер, который добавляет новые данные, модели, DAG-и,
дашборды или целые бизнес-направления.

---

## 1. Главный принцип

Проект слоистый:

```
генерация -> S3 -> raw -> staging -> marts -> BI
                     \-> Spark -> Iceberg -> external catalog
```

Новую функциональность добавляйте **аддитивно**:

- не ломайте существующие 15 supply-chain таблиц;
- не меняйте seed без причины;
- не удаляйте старые модели;
- новые таблицы/модели/чарты добавляйте рядом;
- каждый шаг должен быть идемпотентным.

---

## 2. Куда что добавлять

| Хочу добавить | Куда смотреть |
|---|---|
| Новую supply-chain таблицу | `dbt/scripts/generate_and_upload.py` (`TABLES`, `COLUMN_POOL`) |
| Новое бизнес-направление | новый генератор + loader + prefix + dbt folder + DAG tasks |
| Новую staging-модель | `project/models/staging/` |
| Новую mart-витрину | `project/models/marts/` |
| Новый тест | `schema.yml` рядом с моделями |
| Новую задачу Airflow | `airflow/dags/dbt_supply_chain_dag.py` |
| Новый DAG | `airflow/dags/` |
| Новый чарт/дашборд | `superset/init/create_all_dashboards.py` |
| Новую Iceberg-таблицу | `spark/jobs/etl_supply_chain.py` или новый job |
| Новый сервис | `docker-compose.yml` + docs |

---

## 3. Рецепт: добавить supply-chain таблицу

### 3.1. Генератор

Файл: `dbt/scripts/generate_and_upload.py`.

1. Добавьте таблицу в `TABLES`:

```python
("new_entities", [
    ("entity_name", "name"),
    ("created_at", "datetime"),
    ("amount", "money"),
], [("supplier_id", "suppliers")]),
```

2. Если нужны новые типы колонок — добавьте их в `COLUMN_POOL`.
3. Если нужен новый тип значения — добавьте его в `gen_value` и
   `KIND_TO_SR` в `load_s3_to_starrocks.py`.

### 3.2. Загрузчик

`load_s3_to_starrocks.py` автоматически:

- читает схему из `/tmp/_schema.json`;
- создаёт `raw_new_entities`;
- грузит CSV.

Если появился новый SQL-тип — обновите `KIND_TO_SR`.

### 3.3. dbt

`generate_and_upload.py` сам создаст:

- `project/models/staging/stg_new_entities.sql`;
- строку в `sources.yml`.

Это генерируемые файлы. Если нужна нестандартная staging-логика — создайте
отдельный файл, например `stg_new_entities_custom.sql`, или измените
генератор.

### 3.4. Mart

Создайте `project/models/marts/mart_new_entities.sql`:

```sql
{{ config(
    materialized='table',
    engine='OLAP',
    keys=['entity_id'],
    table_type='PRIMARY',
    distributed_by=['entity_id'],
    buckets=4,
    properties='{"replication_num": "1"}'
) }}

SELECT
    entity_id,
    COUNT(*) AS cnt,
    SUM(amount) AS total_amount
FROM {{ ref('stg_new_entities') }}
GROUP BY entity_id
```

### 3.5. Тесты

Добавьте в `project/models/marts/schema.yml`:

```yaml
  - name: mart_new_entities
    columns:
      - name: entity_id
        tests: [unique, not_null]
```

### 3.6. Проверка

```powershell
docker compose up -d --force-recreate data-init dbt
docker compose logs dbt --tail 100
```

Ожидаемо: новая модель в `PASS`, тесты проходят.

---

## 4. Рецепт: добавить новое бизнес-направление

Пример — retail. Действуйте по шагам.

### 4.1. Выберите prefix

Например:

```
s3://dbt-bucket/finance/stg/{table}/{date}/
```

Не используйте `stg/` — он занят supply chain.

### 4.2. Генератор

Создайте `dbt/scripts/generate_finance.py` по образцу
`generate_retail.py`:

- `SEED` через env;
- `SCHEMAS` с колонками и SQL-типами;
- `random.Random(SEED)`;
- FK-связи;
- `upload_table` с очисткой prefix;
- запись `_finance_schema.json`.

### 4.3. Загрузчик

Создайте `load_finance_to_starrocks.py` по образцу
`load_retail_to_starrocks.py`:

- читает `_finance_schema.json`;
- создаёт `analytics.raw_finance_*`;
- грузит `finance/stg/...`.

### 4.4. dbt

Создайте:

```
project/models/staging/finance/sources.yml
project/models/staging/finance/stg_finance__*.sql
project/models/marts/finance/mart_finance__*.sql
project/models/marts/finance/schema.yml
```

Соглашение об именах:

```
stg_finance__<entity>
mart_finance__<metric>
```

### 4.5. Оркестрация

В `dbt/scripts/init.sh` добавьте шаги:

```bash
python /dbt/scripts/generate_finance.py
python /dbt/scripts/load_finance_to_starrocks.py
```

В `airflow/dags/dbt_supply_chain_dag.py` добавьте `BashOperator`-задачи и
цепочку:

```python
gen_finance >> load_finance >> run
```

### 4.6. BI

Добавьте датасеты, чарты и дашборд в
`superset/init/create_all_dashboards.py`:

- новые `chart_specs`;
- новый dashboard title;
- `find_or_create` уже обеспечивает идемпотентность.

### 4.7. Документация

Обновите:

- `docs/ARCHITECTURE.md` — новый поток;
- `docs/modules/04-data-generation.md` — новые таблицы;
- `docs/modules/03-dbt.md` — новые модели;
- `docs/modules/08-superset.md` — новый дашборд;
- `docs/RUNBOOK.md` — проверки.

---

## 5. Рецепт: добавить mart-витрину

1. Создайте `project/models/marts/mart_<name>.sql`.
2. Используйте `{{ ref('stg_...') }}`.
3. Укажите StarRocks-параметры:

```sql
{{ config(
    materialized='table',
    engine='OLAP',
    keys=['key'],
    table_type='PRIMARY',
    distributed_by=['key'],
    buckets=4,
    properties='{"replication_num": "1"}'
) }}
```

4. Добавьте тесты в `schema.yml`.
5. Запустите:

```powershell
docker compose run --rm --no-deps --entrypoint dbt dbt `
  --profiles-dir /dbt/profiles run --select "+mart_<name>"
```

6. Проверьте:

```sql
SELECT * FROM analytics.mart_<name> LIMIT 10;
```

---

## 6. Рецепт: добавить задачу Airflow

Файл: `airflow/dags/dbt_supply_chain_dag.py`.

```python
new_task = BashOperator(
    task_id="new_task",
    bash_command="python /opt/airflow/dbt/scripts/new_script.py",
    env=ENV,
)

run >> new_task
# или включите в цепочку:
# gen >> load >> new_task >> run >> test
```

Проверка:

```powershell
docker compose restart airflow-scheduler airflow-webserver airflow-worker
docker exec airflow_scheduler airflow dags list-import-errors
docker exec airflow_scheduler airflow dags trigger dbt_supply_chain_pipeline
```

Не забудьте добавить нужные env-переменные в `ENV`.

---

## 7. Рецепт: добавить DAG

1. Создайте `airflow/dags/<name>_dag.py`.
2. Используйте `BashOperator` или `PythonOperator`.
3. Не забудьте `start_date`, `schedule`, `catchup=False`.
4. Перезапустите scheduler/webserver/worker.
5. Проверьте `airflow dags list`.
6. Новый DAG будет на паузе — снимите через UI/CLI.

Если DAG должен запускать Spark, учтите: у Airflow нет Docker socket.
Варианты:

- смонтировать `/var/run/docker.sock` (риск безопасности);
- использовать `SparkSubmitOperator` с отдельным Spark-кластером;
- запускать Spark ETL вне Airflow (текущий вариант).

---

## 8. Рецепт: добавить чарт/дашборд Superset

Файл: `superset/init/create_all_dashboards.py`.

1. Добавьте dataset, если его нет, в `dataset_tables`.
2. Добавьте spec в `chart_specs`:

```python
{
    "name": "RT: New Chart",
    "dataset": "mart_retail__sales_by_month",
    "viz_type": "echarts_timeseries_bar",
    "params": {
        "datasource": ds,
        "viz_type": "echarts_timeseries_bar",
        "x_axis": "month",
        "metrics": [simple_metric("net_revenue", "SUM", "Revenue")],
        "row_limit": 100,
    },
}
```

3. Добавьте чарт в нужный dashboard в `dashboards`.
4. Пересоздайте one-shot:

```powershell
docker compose up -d --force-recreate superset-dashboards
```

5. Проверьте логи и UI.

Идемпотентность уже реализована: повторный запуск обновит чарт, а не
создаст дубликат.

---

## 9. Рецепт: добавить Iceberg-таблицу

Файл: `spark/jobs/etl_supply_chain.py` или новый job.

1. Прочитайте CSV:

```python
df = spark.read.option("header", "true").option("inferSchema", "true") \
    .csv("s3a://dbt-bucket/stg/new_table/*/*.csv")
```

2. Создайте namespace (если нужен новый):

```python
spark.sql("CREATE NAMESPACE IF NOT EXISTS lakehouse.supply_chain")
```

3. Запишите:

```python
df.writeTo("lakehouse.supply_chain.new_table").createOrReplace()
```

4. Проверьте:

```python
spark.sql("SELECT COUNT(*) FROM lakehouse.supply_chain.new_table").show()
```

5. Обновите `verify_iceberg.py`.
6. Если таблица должна быть видна в StarRocks — каталог уже создан;
   проверьте `SHOW TABLES FROM iceberg_lakehouse.supply_chain`.

---

## 10. Рецепт: добавить сервис

1. Добавьте сервис в `docker-compose.yml`.
2. Укажите `image`/`build`, `ports`, `volumes`, `networks`.
3. Добавьте `depends_on` и healthcheck, если возможно.
4. Добавьте переменные в `.env` и `environment`.
5. Проверьте:

```powershell
docker compose config
docker compose up -d <service>
docker compose ps <service>
docker compose logs <service>
```

6. Опишите сервис в `docs/ARCHITECTURE.md` и `docs/modules/01-infrastructure.md`.

---

## 11. Тестирование изменений

Минимальный набор:

```powershell
# 1. Compose
docker compose config --quiet

# 2. Пересборка затронутых сервисов
docker compose up -d --build

# 3. dbt
docker compose run --rm --no-deps --entrypoint dbt dbt `
  --profiles-dir /dbt/profiles run
docker compose run --rm --no-deps --entrypoint dbt dbt `
  --profiles-dir /dbt/profiles test

# 4. Airflow
docker exec airflow_scheduler airflow dags list-import-errors
docker exec airflow_scheduler airflow dags trigger dbt_supply_chain_pipeline

# 5. StarRocks
docker exec starrocks mysql -h 127.0.0.1 -P 9030 -uroot `
  -e "SELECT COUNT(*) FROM analytics.mart_<new>;"

# 6. Superset
# открыть UI и проверить дашборд
```

Полный чек-лист — [`modules/10-checks-and-tests.md`](modules/10-checks-and-tests.md).

---

## 12. Git workflow

### Что коммитить

- исходники (`dbt/`, `project/`, `airflow/`, `spark/`, `superset/`);
- `docker-compose.yml`, `.env` (если это учебные значения);
- документацию;
- отчёты.

### Что не коммитить

- `airflow/logs/`, `project/logs/`;
- `project/target/`;
- `__pycache__/`, `*.pyc`;
- `.user.yml`;
- локальные `.env.local`;
- `node_modules`;
- `.ivy2`.

`.gitignore` уже настроен. Если артефакт был в индексе:

```powershell
git rm -r --cached <path>
```

### Коммит

```powershell
git status
git diff
git add <files>
git commit -m "feat: ..."
git push
```

Не коммитьте секреты. Если нужен пример — используйте `.env.example`.

---

## 13. Конфигурация и секреты

- В учебном проекте credentials лежат в `.env` и в DAG `ENV`.
- В production:
  - Airflow Connections/Variables;
  - Docker secrets / Vault;
  - отдельные S3-ключи для Spark/StarRocks/генераторов;
  - TLS для MinIO/StarRocks/Superset.
- При изменении `.env` не забудьте:
  - пересоздать контейнеры;
  - синхронизировать `ENV` в DAG (он захардкожен).

---

## 14. Версии и обновления

| Компонент | Версия | Почему зафиксирована |
|---|---|---|
| Airflow | 2.10.5 | совместимость с dbt/Python 3.11 |
| dbt-core | 1.6.2 | стабильная связка |
| dbt-starrocks | 1.6.2 | 1.7+ требует проверки |
| StarRocks | 3.4 | allin1, поддержка `FILES()` |
| Spark | 3.5.6 | совместимость с Iceberg 1.4.3 |
| Iceberg | 1.4.3 | проверенная связка |
| Superset | 4.1.2 | API дашбордов |

Перед обновлением:

1. прочитайте changelog;
2. поднимите отдельную ветку;
3. обновите одну зависимость;
4. прогоните dbt/Airflow/Superset проверки;
5. обновите документацию.

Особенно осторожно с `dbt-starrocks` и `iceberg-rest` (fixture).

---

## 15. Roadmap-идеи

Из корневого README и текущего состояния:

- инкрементальный ETL (`MERGE INTO`) вместо `createOrReplace`;
- CDC-пайплайн (insert/update/delete);
- партиционирование Iceberg по дате;
- compaction мелких Parquet-файлов;
- dbt поверх Iceberg как source;
- `spark_etl_dag` через SparkSubmitOperator;
- scheduled reports и алерты в Superset;
- Telegram/Slack-алерты из Airflow;
- Prometheus + Grafana;
- CI/CD GitHub Actions;
- Terraform для инфраструктуры;
- отдельные S3-ключи и секреты.

---

## 16. Чек-лист перед PR

- [ ] `docker compose config` без ошибок.
- [ ] `docker compose up -d --build` проходит.
- [ ] `docker compose ps -a`: long-running Up, one-shot Exited (0).
- [ ] dbt `run`/`test` без ошибок.
- [ ] Airflow DAG импортируется, run success.
- [ ] StarRocks counts корректны.
- [ ] Spark/Iceberg (если затронуто) работает.
- [ ] Superset дашборды открываются.
- [ ] Нет логов/`target`/`__pycache__` в git.
- [ ] Документация обновлена.
- [ ] Нет запуска legacy-генераторов.
