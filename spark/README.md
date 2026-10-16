# spark — Lakehouse на Spark + Iceberg

Модуль отвечает за построение **lakehouse-слоя** поверх MinIO.
Spark читает CSV из S3, пишет Iceberg-таблицы (Parquet + метаданные),
а StarRocks читает их через external catalog — **без копирования данных**.

Ключевая идея: **compute-storage separation**.
Данные лежат в S3, вычислители (Spark, StarRocks) работают с ними независимо.

---

## Структура

```
spark/
├── README.md                        # Этот файл
├── conf/
│   └── spark-defaults.conf          # Конфиг Spark (Iceberg + MinIO)
├── jobs/
│   ├── etl_supply_chain.py          # ETL: CSV -> Iceberg
│   └── verify_iceberg.py            # Проверка: что таблицы создались
└── init-starrocks.sql               # SQL для external catalog в StarRocks
```

---

## Зачем это нужно

Модуль решает три задачи:

1. **Хранение** — Iceberg-таблицы в MinIO (Parquet + метаданные).
2. **Обработка** — Spark читает CSV и пишет Iceberg.
3. **Чтение** — StarRocks через REST catalog читает Iceberg напрямую.

Что это даёт:

- **Единый источник данных** — и Spark, и StarRocks, и любой другой движок
  видят одни и те же таблицы.
- **Open table format** — Iceberg не привязан к вендору.
- **Снапшоты и time-travel** — можно читать данные «на момент времени».
- **Схема-эволюция** — добавление колонок без перезаписи.
- **Партиционирование** — ускорение запросов без перестройки таблицы.

---

## Архитектура

```
+-------------+     +--------------+     +------------+
|   Spark     |---->|  Iceberg     |<----|  Iceberg   |
|  (compute)  |     |  (format)    |     |   REST     |
+-------------+     +--------------+     | (metadata) |
                          |              +------------+
                          v
                   +--------------+
                   |   MinIO      |
                   |   (storage)  |
                   +------+-------+
                          |
                          v
                   +--------------+
                   |  StarRocks   |
                   |  (reader)    |
                   +--------------+
```

**Компоненты:**

| Компонент     | Роль                                              |
|---------------|---------------------------------------------------|
| Spark 3.5.6   | ETL-движок: чтение CSV, запись Iceberg, MERGE     |
| Iceberg 1.4.3 | Open table format: описание таблиц поверх Parquet |
| Iceberg REST  | REST-каталог: единая точка для метаданных         |
| MinIO         | S3-хранилище: Parquet-файлы + метаданные Iceberg  |
| StarRocks     | Читает Iceberg через `CREATE EXTERNAL CATALOG`    |

---

## conf/spark-defaults.conf

**Назначение:** единая точка настройки Spark. Монтируется в контейнер
`spark-iceberg` через volume.

**Полный файл:**

```properties
# ---------- Iceberg + REST Catalog ----------
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

# ---------- Hadoop / S3A (MinIO) ----------
spark.hadoop.fs.s3a.endpoint=http://minio:9000
spark.hadoop.fs.s3a.access.key=minioadmin
spark.hadoop.fs.s3a.secret.key=minioadmin
spark.hadoop.fs.s3a.path.style.access=true
spark.hadoop.fs.s3a.connection.ssl.enabled=false
spark.hadoop.fs.s3a.impl=org.apache.hadoop.fs.s3a.S3AFileSystem

# ---------- Библиотеки (Iceberg + Hadoop AWS) ----------
spark.jars.packages=org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.4.3,org.apache.iceberg:iceberg-aws-bundle:1.4.3,org.apache.hadoop:hadoop-aws:3.3.4,com.amazonaws:aws-java-sdk-bundle:1.12.262

# ---------- Кэш JAR-ов во временную папку ----------
spark.jars.ivy=/tmp/.ivy2

# ---------- Лимиты памяти (Docker 4.8 GB) ----------
spark.driver.memory=512m
spark.executor.memory=512m
spark.driver.cores=1
spark.executor.cores=1
spark.cores.max=2
spark.sql.shuffle.partitions=4
spark.default.parallelism=4

# ---------- Прочее ----------
spark.sql.warehouse.dir=s3a://dbt-bucket/warehouse
spark.eventLog.enabled=false
spark.ui.enabled=true
spark.ui.port=4040
```

**Построчно:**

| Параметр                                              | Что делает                                             |
|-------------------------------------------------------|--------------------------------------------------------|
| spark.sql.extensions=...IcebergSparkSessionExtensions | Включает Iceberg-расширения SQL в Spark                |
| spark.sql.catalog.lakehouse=...SparkCatalog           | Регистрирует каталог с именем `lakehouse`              |
| spark.sql.catalog.lakehouse.type=rest                 | Тип каталога — REST (удалённый сервис)                 |
| spark.sql.catalog.lakehouse.uri=...                   | URL Iceberg REST-каталога                              |
| spark.sql.catalog.lakehouse.warehouse=...             | Где Iceberg хранит все таблицы                         |
| spark.sql.catalog.lakehouse.io-impl=...S3FileIO       | Класс для чтения/записи S3                             |
| spark.sql.catalog.lakehouse.s3.endpoint=...           | Endpoint MinIO                                         |
| spark.sql.catalog.lakehouse.s3.path-style-access=true | Path-style URL (обязательно для MinIO)                 |
| spark.sql.catalog.lakehouse.s3.access-key-id=...      | Логин MinIO                                            |
| spark.sql.catalog.lakehouse.s3.secret-access-key=...  | Пароль MinIO                                           |
| spark.sql.defaultCatalog=lakehouse                    | Каталог по умолчанию                                   |
| spark.hadoop.fs.s3a.endpoint=...                      | Endpoint MinIO для старого S3A API                     |
| spark.hadoop.fs.s3a.access.key=...                    | Ключ для S3A                                           |
| spark.hadoop.fs.s3a.secret.key=...                    | Секрет для S3A                                         |
| spark.hadoop.fs.s3a.path.style.access=true            | Path-style для S3A                                     |
| spark.hadoop.fs.s3a.connection.ssl.enabled=false      | HTTP вместо HTTPS                                      |
| spark.hadoop.fs.s3a.impl=...S3AFileSystem             | Класс файловой системы                                 |
| spark.jars.packages=...                               | Список Maven-зависимостей для автозагрузки             |
| spark.jars.ivy=/tmp/.ivy2                             | Куда кэшировать JAR-ы (обход PermissionError)          |
| spark.driver.memory=512m                              | Лимит памяти драйвера                                  |
| spark.executor.memory=512m                            | Лимит памяти executor'а                                |
| spark.driver.cores=1                                  | Одно ядро на драйвер                                   |
| spark.executor.cores=1                                | Одно ядро на executor                                  |
| spark.cores.max=2                                     | Не более 2 ядер всего                                  |
| spark.sql.shuffle.partitions=4                        | Минимум партиций (данные маленькие)                    |
| spark.default.parallelism=4                           | Уровень параллелизма                                   |
| spark.sql.warehouse.dir=...                           | Папка warehouse (в S3)                                 |
| spark.eventLog.enabled=false                          | Отключаем event log (не нужен)                         |
| spark.ui.enabled=true                                 | Spark Web UI доступен                                  |
| spark.ui.port=4040                                    | Порт UI                                                |

**Критичные моменты:**

1. **`hadoop-aws:3.3.4`** — без него `ClassNotFoundException: S3AFileSystem`.
   Базовый образ `apache/spark:3.5.6` НЕ содержит Hadoop AWS.

2. **`aws-java-sdk-bundle:1.12.262`** — нужен для подписи запросов к S3.

3. **`spark.jars.ivy=/tmp/.ivy2`** — по умолчанию Spark пытается писать в
   `/home/spark/.ivy2`, где нет прав. Даёт ошибку `PermissionError`.

4. **`path-style-access=true`** — MinIO не поддерживает virtual-hosted style.

5. **`enable_ssl=false`** — MinIO работает по HTTP, не HTTPS.

6. **`warehouse=s3://dbt-bucket/warehouse`** (схема `s3://`, а не `s3a://`) —
   это путь для Iceberg, Spark FileIO его знает.

---

## jobs/etl_supply_chain.py

**Назначение:** ETL-скрипт. Читает CSV из MinIO, пишет Iceberg-таблицу.

**Логика работы:**

```python
# 1. Создать SparkSession
spark = SparkSession.builder.appName("etl_supply_chain").getOrCreate()

# 2. Создать namespace в Iceberg
spark.sql("CREATE NAMESPACE IF NOT EXISTS lakehouse.supply_chain")

# 3. Прочитать CSV из MinIO
df = spark.read \
    .option("header", "true") \
    .option("inferSchema", "true") \
    .csv("s3a://dbt-bucket/stg/suppliers/*/*.csv")

# 4. Записать в Iceberg
df.writeTo("lakehouse.supply_chain.suppliers").createOrReplace()

# 5. Проверить
spark.sql("SELECT COUNT(*) FROM lakehouse.supply_chain.suppliers").show()
```

**Как запускать:**

```powershell
docker exec -it spark_iceberg /opt/spark/bin/spark-submit /opt/spark/jobs/etl_supply_chain.py
```

**Первый запуск:**

- Spark скачает Maven-зависимости (~70 МБ) — займёт 2–5 минут.
- Дальше кэш в `/tmp/.ivy2` — следующие запуски за 30–60 секунд.

**Что произойдёт в MinIO:**

```
s3://dbt-bucket/warehouse/
└── supply_chain.db/
    └── suppliers/
        ├── data/
        │   └── 00000-0-xxxx.parquet
        └── metadata/
            ├── v1.metadata.json
            └── snap-xxxx.avro
```

**Фазы скрипта:**

| Фаза | Что делает                                |
|------|-------------------------------------------|
| 1    | Создаёт SparkSession                      |
| 2    | Создаёт namespace `lakehouse.supply_chain`|
| 3    | Читает CSV из `s3a://dbt-bucket/stg/suppliers/*/*.csv` |
| 4    | Пишет в Iceberg (`createOrReplace`)       |
| 5    | Выводит COUNT и первые 3 строки           |

**Опция `createOrReplace`:**

Полностью пересоздаёт таблицу при каждом запуске. Подходит для учебного
проекта, но для production нужен `MERGE INTO` (инкремент) — см. Roadmap.

**Инкрементальный вариант:**

Если нужно — можно заменить на:

```sql
MERGE INTO lakehouse.supply_chain.suppliers AS t
USING new_data AS s
ON t.supplier_id = s.supplier_id
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *
```

Это работает через Spark SQL и требует watermark (по `created_at`).

---

## jobs/verify_iceberg.py

**Назначение:** проверка, что Iceberg-таблицы создались и данные читаются.

**Что делает:**

```python
# Список каталогов
spark.sql("SHOW CATALOGS").show()

# Список namespaces
spark.sql("SHOW NAMESPACES IN lakehouse").show()

# Список таблиц
spark.sql("SHOW TABLES IN lakehouse.supply_chain").show()

# Данные
spark.sql("SELECT * FROM lakehouse.supply_chain.suppliers LIMIT 5").show()
```

**Как запускать:**

```powershell
docker exec -it spark_iceberg /opt/spark/bin/spark-submit /opt/spark/jobs/verify_iceberg.py
```

Или через `spark-sql`:

```powershell
docker exec -it spark_iceberg /opt/spark/bin/spark-sql
# spark-sql> SHOW CATALOGS;
# spark-sql> SELECT COUNT(*) FROM lakehouse.supply_chain.suppliers;
# spark-sql> EXIT;
```

---

## init-starrocks.sql

**Назначение:** подключает StarRocks к Iceberg-каталогу.

**Полный файл:**

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

**Построчно:**

| Строка                                | Что делает                                      |
|---------------------------------------|-------------------------------------------------|
| CREATE EXTERNAL CATALOG IF NOT EXISTS | Идемпотентно создаёт каталог                    |
| "type" = "iceberg"                    | Тип каталога — Iceberg                          |
| "iceberg.catalog.type" = "rest"       | REST-каталог (не Hive, не Glue)                 |
| "iceberg.catalog.uri" = ...           | URL Iceberg REST (внутри сети — `iceberg-rest`) |
| "aws.s3.endpoint" = ...               | MinIO endpoint                                  |
| "aws.s3.access_key" = ...             | Логин MinIO                                     |
| "aws.s3.secret_key" = ...             | Пароль MinIO                                    |
| "aws.s3.enable_path_style_access"     | Path-style URL (обязательно для MinIO)          |
| "aws.s3.enable_ssl" = "false"         | HTTP, не HTTPS                                  |

**Как применить:**

```powershell
Get-Content spark\init-starrocks.sql | docker exec -i starrocks mysql -h 127.0.0.1 -P 9030 -uroot
```

Или через `cmd`:

```powershell
cmd /c "docker exec -i starrocks mysql -h 127.0.0.1 -P 9030 -uroot < spark\init-starrocks.sql"
```

В PowerShell `<` не работает — используем `Get-Content | ...`.

**После этого StarRocks видит:**

```sql
SHOW CATALOGS;                                     -- iceberg_lakehouse в списке
SHOW DATABASES FROM iceberg_lakehouse;             -- supply_chain
SHOW TABLES FROM iceberg_lakehouse.supply_chain;   -- suppliers
```

**Запросы:**

```sql
-- Простой SELECT
SELECT * FROM iceberg_lakehouse.supply_chain.suppliers LIMIT 10;

-- Агрегация
SELECT country, COUNT(*)
FROM iceberg_lakehouse.supply_chain.suppliers
GROUP BY country;

-- JOIN с обычной таблицей StarRocks
SELECT s.supplier_name, o.total_price
FROM iceberg_lakehouse.supply_chain.suppliers s
JOIN analytics.raw_supply_orders o ON o.supplier_id = s.supplier_id
LIMIT 20;
```

**Ключевое:** StarRocks **не копирует** данные из Iceberg — он читает
Parquet **напрямую** из MinIO. Запрос идёт:
REST → метаданные Iceberg → Parquet-файлы в MinIO → результат.

---

## Как это связано с docker-compose

Сервис `iceberg-rest`:

```yaml
iceberg-rest:
  image: apache/iceberg-rest-fixture:1.10.1
  environment:
    - CATALOG_WAREHOUSE=s3://dbt-bucket/warehouse
    - CATALOG_IO__IMPL=org.apache.iceberg.aws.s3.S3FileIO
    - CATALOG_S3_ENDPOINT=http://minio:9000
    - CATALOG_S3_ACCESS__KEY__ID=minioadmin
    - CATALOG_S3_SECRET__ACCESS__KEY=minioadmin
    - CATALOG_S3_PATH__STYLE__ACCESS=true
  ports: ["8181:8181"]
```

Сервис `spark-iceberg`:

```yaml
spark-iceberg:
  image: apache/spark:3.5.6
  depends_on: [iceberg-rest, minio]
  volumes:
    - ./spark/conf/spark-defaults.conf:/opt/spark/conf/spark-defaults.conf
    - ./spark/jobs:/opt/spark/jobs
  ports:
    - "8888:8888"    # Jupyter
    - "8082:8080"    # Spark Master UI
    - "10000:10000"  # Spark Thrift Server
    - "4040:4040"    # Spark UI
  command: ["tail", "-f", "/dev/null"]   # держим контейнер живым
```

**Ключевые моменты:**

1. **`iceberg-rest` использует `apache/iceberg-rest-fixture`** —
   официальный образ Apache, скачивается стабильно.
   Не `tabulario/iceberg-rest` (с ним была ошибка `failed size validation`).

2. **Двойное подчёркивание `__` в env** — это способ передать вложенные
   параметры Iceberg. `CATALOG_S3_PATH__STYLE__ACCESS=true` = property
   `s3.path-style-access=true`.

3. **`tail -f /dev/null`** — контейнер Spark живёт, но ничего не делает.
   Команды подаём через `docker exec` (spark-submit, spark-sql).

4. **Volume `spark-defaults.conf`** монтирует конфиг внутрь контейнера —
   Spark читает его при старте `spark-submit`.

5. **Volume `./spark/jobs`** — папка со скриптами ETL.

---

## Отладка

### Проверить, что Spark видит Iceberg-каталог

```powershell
docker exec -it spark_iceberg /opt/spark/bin/spark-sql -e "SHOW CATALOGS"
```

Ожидаемо:

```
lakehouse
spark_catalog
```

### Посмотреть Maven-кэш

```powershell
docker exec -it spark_iceberg ls -lh /tmp/.ivy2/jars/
```

Должны быть JAR-ы: `iceberg-spark-runtime`, `iceberg-aws-bundle`,
`hadoop-aws`, `aws-java-sdk-bundle`.

### Посмотреть MinIO warehouse

```powershell
docker exec dbt_minio mc ls --recursive local/dbt-bucket/warehouse/
```

Должны быть папки `supply_chain.db/`, внутри — `suppliers/metadata/`, `data/`.

### Проверить external catalog в StarRocks

```powershell
docker exec starrocks mysql -h 127.0.0.1 -P 9030 -uroot -e "SHOW CATALOGS"
docker exec starrocks mysql -h 127.0.0.1 -P 9030 -uroot -e "SHOW DATABASES FROM iceberg_lakehouse"
```

### Логи контейнера

```powershell
docker compose logs spark-iceberg --tail 50
docker compose logs iceberg-rest --tail 50
```

### Войти в контейнер

```powershell
docker exec -it spark_iceberg bash
```

Внутри:

```bash
cat /opt/spark/conf/spark-defaults.conf
ls /opt/spark/jobs/
ls /tmp/.ivy2/jars/
```

---

## Частые проблемы

| Симптом                                          | Причина                          | Решение                                                            |
|--------------------------------------------------|----------------------------------|--------------------------------------------------------------------|
| `ClassNotFoundException: S3AFileSystem`          | Нет hadoop-aws.jar               | Добавить `org.apache.hadoop:hadoop-aws:3.3.4` в spark.jars.packages |
| `FileNotFoundException: /home/spark/.ivy2/...`   | Нет прав на запись               | `spark.jars.ivy=/tmp/.ivy2`                                        |
| `Unable to connect to REST catalog`              | iceberg-rest не запущен          | `docker compose up -d iceberg-rest`                                |
| `scheme is null` при чтении Iceberg              | Забыли path-style access         | `"aws.s3.enable_path_style_access" = "true"`                       |
| spark-sql зависает на 5+ минут                   | Качает Maven-зависимости         | Подождать; проверить сеть                                          |
| `Permission denied: /tmp/.ivy2/...`              | Пользователь spark без прав      | `docker exec -u root spark_iceberg chmod 777 /tmp/.ivy2`           |
| `The container is not running`                   | spark-iceberg упал (OOM)         | Проверить `docker stats`                                           |
| StarRocks не видит Iceberg-таблицу               | Кэш метаданных                   | `REFRESH EXTERNAL TABLE iceberg_lakehouse.supply_chain.suppliers`  |

---

## Как это работает вместе с другими модулями

Поток данных в проекте:

```
data-init (dbt/scripts/generate_and_upload.py)
    |
    v
MinIO (s3://dbt-bucket/stg/{table}/{date}/*.csv)
    |
    +--> load_s3_to_starrocks.py -> raw_* в StarRocks  (классический путь)
    |
    +--> Spark ETL (spark/jobs/etl_supply_chain.py)  (lakehouse-путь)
             |
             v
         Iceberg (s3://dbt-bucket/warehouse/*.db/*)
             |
             v
         StarRocks external catalog (iceberg_lakehouse)
             |
             v
         Superset (визуализация)
```

**Два независимых пути:**

1. **Классический DWH:** CSV → StarRocks (raw_*) → dbt (stg_* + mart_*) → Superset.
2. **Lakehouse:** CSV → Spark → Iceberg (MinIO) → StarRocks external catalog → Superset.

Данные в S3 — общие для обоих путей.

---

## Ссылки

- Spark SQL Guide: https://spark.apache.org/docs/latest/sql-programming-guide.html
- Iceberg Spark Docs: https://iceberg.apache.org/docs/latest/spark-getting-started/
- Iceberg REST Catalog: https://iceberg.apache.org/docs/latest/rest-catalog/
- StarRocks Iceberg Catalog: https://docs.starrocks.io/docs/data_source/catalog/iceberg_catalog/
- Проект в целом: см. ../README.md