# Модуль 02 — Airflow

**Файлы:** `airflow/Dockerfile`, `airflow/dags/dbt_supply_chain_dag.py`.

---

## 1. DAG

`dbt_supply_chain_pipeline`:

```
generate_and_upload
  -> generate_retail
  -> spark_etl_to_iceberg
  -> dbt_run
  -> dbt_test
```

- schedule `0 3 * * *`;
- `catchup=False`, `max_active_runs=1`;
- при создании DAG на паузе.

---

## 2. Образ Airflow

База: `apache/airflow:2.10.5-python3.11`.

Установлено:

- Java 17 (`openjdk-17-jre-headless`);
- `dbt-core==1.6.2`;
- `dbt-trino==1.6.2`;
- `pyspark==3.5.6`;
- boto3, botocore, pandas, requests.

StarRocks-драйверов и `dbt-starrocks` больше нет.

---

## 3. Spark в Airflow

Airflow worker запускает Spark локально:

```bash
spark-submit \
  --properties-file /opt/airflow/spark/conf/spark-defaults.conf \
  --master 'local[2]' --driver-memory 3g \
  /opt/airflow/spark/jobs/etl_all_to_iceberg.py
```

Volumes worker:

- `./spark/conf:/opt/airflow/spark/conf:ro`;
- `./spark/jobs:/opt/airflow/spark/jobs:ro`;
- `./dbt/scripts`, `./dbt/profiles`, `./project`.

---

## 4. dbt в Airflow

`dbt_run` / `dbt_test` используют профиль Trino:

- `TRINO_HOST=trino`;
- `TRINO_PORT=8080`;
- `TRINO_CATALOG=iceberg`;
- `TRINO_SCHEMA=analytics`.

---

## 5. Проверка

```powershell
docker exec airflow_scheduler airflow dags list
docker exec airflow_scheduler airflow dags list-import-errors
docker exec airflow_scheduler airflow dags unpause dbt_supply_chain_pipeline
docker exec airflow_scheduler airflow dags trigger dbt_supply_chain_pipeline
docker exec airflow_scheduler airflow dags list-runs -d dbt_supply_chain_pipeline
```

---

## 6. Вход

- http://localhost:8080
- admin / admin

При ошибке `scrypt`:

```powershell
docker exec airflow_webserver airflow users reset-password `
  --username admin --password admin
```

---

## 7. Ограничения

- Spark в worker — `local[2]`, не отдельный кластер.
- Тяжёлый Spark job может конкурировать с Airflow за память.
- `iceberg-rest-fixture` — учебный каталог.

---

## 8. Связанные документы

- [`05-trino.md`](05-trino.md)
- [`06-spark-iceberg.md`](06-spark-iceberg.md)
- [`../RUNBOOK.md`](../RUNBOOK.md)
