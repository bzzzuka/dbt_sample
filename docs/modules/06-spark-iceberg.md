# Модуль 06 — Spark + Iceberg

**Файлы модуля:**

- `spark/conf/spark-defaults.conf`
- `spark/jobs/etl_supply_chain.py`
- `spark/jobs/verify_iceberg.py`
- `spark/init-starrocks.sql`
- сервисы `spark-iceberg`, `iceberg-rest` в `docker-compose.yml`

---

## 1. Роль модуля

Модуль строит lakehouse-слой:

```
CSV в MinIO
  -> Spark
  -> Iceberg table (Parquet + metadata) в MinIO
  -> Iceberg REST catalog
  -> StarRocks external catalog
```

Ключевая идея — **compute-storage separation**: данные лежат в S3, Spark
их обрабатывает, StarRocks читает напрямую, без копирования в свою БД.

---

## 2. Сервисы

| Сервис | Образ | Роль | Порт |
|---|---|---|---|
| `iceberg-rest` | `apache/iceberg-rest-fixture:1.10.1` | REST-каталог метаданных | 8181 |
| `spark-iceberg` | `apache/spark:3.5.6` | Контейнер для `spark-submit` | 4040, 8082, 8888, 10000 |

`spark-iceberg` не запускает Spark Master/Thrift/Jupyter. Он держится
командой `tail -f /dev/null`, а команды выполняются через `docker exec`.

Порты 8082/8888/10000 проброшены «на будущее», но соответствующие сервисы
не запущены. Реально используется 4040 — Spark UI во время job.

---

## 3. Конфигурация Spark

Файл: `spark/conf/spark-defaults.conf`.

Основное:

```properties
spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions
spark.sql.catalog.lakehouse=org.apache.iceberg.spark.SparkCatalog
spark.sql.catalog.lakehouse.type=rest
spark.sql.catalog.lakehouse.uri=http://iceberg-rest:8181
spark.sql.catalog.lakehouse.warehouse=s3://dbt-bucket/warehouse
spark.sql.catalog.lakehouse.io-impl=org.apache.iceberg.aws.s3.S3FileIO
spark.sql.catalog.lakehouse.s3.endpoint=http://minio:9000
spark.sql.catalog.lakehouse.s3.path-style-access=true
spark.sql.catalog.lakehouse.s3.access-key-id=minioadmin
spark.sql.catalog.lakehouse.s3.secret-access-key=minioadmin
spark.sql.defaultCatalog=lakehouse
```

Также:

- S3A-настройки для `s3a://`;
- Maven-пакеты Iceberg 1.4.3, hadoop-aws 3.3.4, aws-java-sdk-bundle;
- Ivy cache `/tmp/.ivy2`;
- лимиты памяти 512m;
- `spark.sql.shuffle.partitions=4`.

### Почему `s3://` и `s3a://`

- `warehouse` для Iceberg использует `s3://` — Iceberg S3FileIO понимает;
- чтение CSV через Spark Hadoop использует `s3a://`.

---

## 4. ETL: `etl_supply_chain.py`

Файл: `spark/jobs/etl_supply_chain.py`.

Что делает:

1. создаёт `SparkSession`;
2. `CREATE NAMESPACE IF NOT EXISTS lakehouse.supply_chain`;
3. читает CSV:

```python
spark.read \
  .option("header", "true") \
  .option("inferSchema", "true") \
  .csv("s3a://dbt-bucket/stg/suppliers/*/*.csv")
```

4. пишет Iceberg:

```python
df.writeTo("lakehouse.supply_chain.suppliers").createOrReplace()
```

5. проверяет `COUNT(*)` и первые строки;
6. показывает таблицы.

Особенности:

- обрабатывается **только `suppliers`**;
- `createOrReplace` полностью пересоздаёт таблицу при каждом запуске;
- для production нужен `MERGE INTO`/incremental, но в учебном проекте
  используется полная перезапись.

Запуск:

```powershell
docker exec spark_iceberg /opt/spark/bin/spark-submit `
  /opt/spark/jobs/etl_supply_chain.py
```

Первый запуск скачивает Maven-зависимости (фактически ~300+ МБ), затем
кэш `/tmp/.ivy2` ускоряет запуск.

---

## 5. Проверка: `verify_iceberg.py`

Файл: `spark/jobs/verify_iceberg.py`.

Команды:

```python
SHOW CATALOGS
SHOW NAMESPACES IN lakehouse
SHOW TABLES IN lakehouse.supply_chain
SELECT * FROM lakehouse.supply_chain.suppliers LIMIT 5
```

Запуск:

```powershell
docker exec spark_iceberg /opt/spark/bin/spark-submit `
  /opt/spark/jobs/verify_iceberg.py
```

Ожидаемо: каталог `lakehouse`, namespace `supply_chain`, таблица
`suppliers`, данные читаются.

---

## 6. StarRocks external catalog

Файл: `spark/init-starrocks.sql`.

```sql
CREATE EXTERNAL CATALOG IF NOT EXISTS iceberg_lakehouse
PROPERTIES (
  "type" = "iceberg",
  "iceberg.catalog.type" = "rest",
  "iceberg.catalog.uri" = "http://iceberg-rest:8181",
  "aws.s3.endpoint" = "http://minio:9000",
  "aws.s3.access_key" = "minioadmin",
  "aws.s3.secret_key" = "minioadmin",
  "aws.s3.enable_path_style_access" = "true",
  "aws.s3.enable_ssl" = "false"
);
```

Применить:

```powershell
Get-Content -Raw spark\init-starrocks.sql | docker exec -i starrocks mysql `
  -h 127.0.0.1 -P 9030 -uroot
```

Проверить:

```powershell
docker exec starrocks mysql -h 127.0.0.1 -P 9030 -uroot -e "SHOW CATALOGS;"
docker exec starrocks mysql -h 127.0.0.1 -P 9030 -uroot -e "SELECT COUNT(*) FROM iceberg_lakehouse.supply_chain.suppliers;"
```

---

## 7. Где лежат данные в MinIO

```
s3://dbt-bucket/warehouse/
└── supply_chain.db/
    └── suppliers/
        ├── data/
        │   └── *.parquet
        └── metadata/
            ├── *.metadata.json
            └── *.avro
```

---

## 8. Важное ограничение: метаданные REST fixture

`apache/iceberg-rest-fixture` хранит каталог в SQLite внутри контейнера:
`/tmp/iceberg_catalog.db`.

Следствие:

- после **пересоздания контейнера** `iceberg-rest` каталог пуст;
- Parquet-файлы в MinIO остаются, но Iceberg-таблица «исчезает»;
- нужно повторно выполнить `etl_supply_chain.py`;
- определение `iceberg_lakehouse` в StarRocks сохраняется в volume
  `starrocks_data`.

Это известное ограничение fixture, а не production-решение.

---

## 9. Как проверять

```powershell
# 1. Контейнеры
docker compose ps spark-iceberg iceberg-rest

# 2. ETL
docker exec spark_iceberg /opt/spark/bin/spark-submit `
  /opt/spark/jobs/etl_supply_chain.py

# 3. Проверка Spark
docker exec spark_iceberg /opt/spark/bin/spark-submit `
  /opt/spark/jobs/verify_iceberg.py

# 4. Проверка StarRocks
docker exec starrocks mysql -h 127.0.0.1 -P 9030 -uroot `
  -e "SELECT COUNT(*) FROM iceberg_lakehouse.supply_chain.suppliers;"

# 5. MinIO
docker exec dbt_minio mc alias set local http://localhost:9000 minioadmin minioadmin
docker exec dbt_minio mc ls --recursive local/dbt-bucket/warehouse/
```

---

## 10. Ограничения

1. Iceberg REST fixture не production-ready.
2. Метаданные каталога теряются при пересоздании контейнера.
3. ETL переносит только `suppliers`.
4. Нет Airflow DAG для Spark — запуск вручную.
5. `createOrReplace` — полная перезапись, не incremental.
6. Maven-зависимости скачиваются при первом запуске.
7. Spark UI 4040 доступен только во время job.
8. Память ограничена 512m; для больших данных нужно увеличивать.

---

## 11. Частые ошибки

| Ошибка | Причина | Решение |
|---|---|---|
| `ClassNotFoundException: S3AFileSystem` | нет hadoop-aws | проверить `spark.jars.packages` |
| `FileNotFoundException: /home/spark/.ivy2` | нет прав | `spark.jars.ivy=/tmp/.ivy2` |
| `Unable to connect to REST catalog` | `iceberg-rest` не запущен | `docker compose up -d iceberg-rest` |
| `NoSuchNamespaceException` | REST потерял metadata | повторно ETL |
| `scheme is null` | path-style/endpoint | проверить S3-настройки |
| Spark долго стартует | качает Maven | подождать, кэш |
| `Permission denied: /tmp/.ivy2` | права | `docker exec -u root ... chmod` |
| StarRocks не видит таблицу | кэш/каталог | `REFRESH EXTERNAL TABLE` |
| `Exited 137` | OOM | увеличить память |

---

## 12. Связанные документы

- [`05-starrocks.md`](05-starrocks.md)
- [`07-minio.md`](07-minio.md)
- [`../RUNBOOK.md`](../RUNBOOK.md)
- [`../DEVELOPMENT_GUIDE.md`](../DEVELOPMENT_GUIDE.md)
