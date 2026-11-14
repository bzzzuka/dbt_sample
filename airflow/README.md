# Airflow (Trino stack)

DAG: `dbt_supply_chain_pipeline`.

```
generate_and_upload
  -> generate_retail
  -> spark_etl_to_iceberg
  -> dbt_run
  -> dbt_test
```

Airflow worker содержит `dbt-trino`, `pyspark 3.5.6` и Java 17. Spark
запускается локально:

```bash
spark-submit \
  --properties-file /opt/airflow/spark/conf/spark-defaults.conf \
  --master 'local[2]' --driver-memory 3g \
  /opt/airflow/spark/jobs/etl_all_to_iceberg.py
```

Вход: http://localhost:8080, admin/admin.

StarRocks-задач и `dbt-starrocks` больше нет.
