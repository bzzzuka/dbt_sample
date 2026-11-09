# Модуль 07 — MinIO (S3-хранилище)

**Файлы модуля:**

- сервис `minio` в `docker-compose.yml`
- `dbt/scripts/generate_and_upload.py`
- `dbt/scripts/generate_retail.py`
- `dbt/scripts/load_s3_to_starrocks.py`
- `dbt/scripts/load_retail_to_starrocks.py`
- `spark/conf/spark-defaults.conf`
- `spark/init-starrocks.sql`

---

## 1. Роль MinIO

MinIO — S3-совместимое хранилище. В нём лежат:

- CSV supply chain;
- CSV retail;
- Iceberg warehouse (Parquet + metadata).

Один bucket `dbt-bucket` используется всеми слоями. Разделение — по
префиксам.

---

## 2. Запуск и доступ

Образ: `ghcr.io/coollabsio/minio:latest`.

| Параметр | Значение |
|---|---|
| S3 API | http://localhost:9000 |
| Console | http://localhost:9001 |
| Логин | `minioadmin` |
| Пароль | `minioadmin` |
| Bucket | `dbt-bucket` |
| Region | `us-east-1` |

Healthcheck: `mc ready local`.

Проверить:

```powershell
docker compose ps minio
Invoke-WebRequest -UseBasicParsing http://localhost:9000/minio/health/live
```

---

## 3. Структура bucket

```
dbt-bucket/
├── stg/                          # supply chain CSV
│   ├── suppliers/
│   │   └── 2026-11-08/
│   │       ├── suppliers_part_001.csv
│   │       └── suppliers_part_002.csv
│   ├── supply_orders/
│   └── ...
├── retail/                       # retail CSV
│   └── stg/
│       ├── orders/
│       │   └── 2026-11-08/
│       │       └── orders_part_001.csv
│       └── customers/
└── warehouse/                    # Iceberg
    └── supply_chain.db/
        └── suppliers/
            ├── data/*.parquet
            └── metadata/*.json, *.avro
```

### Почему `retail/stg`, а не `stg/retail`

Supply chain generator использует `stg/{table}`. Retail вынесен в
`retail/stg/{table}`, чтобы:

- не пересекаться по именам;
- можно было чистить retail отдельно;
- было видно направление в S3-браузере.

---

## 4. `mc` — CLI MinIO

`mc` находится внутри контейнера `dbt_minio`. Alias `local` **не
сохраняется** между пересозданиями, поэтому настраивайте его после
`docker compose up`:

```powershell
docker exec dbt_minio mc alias set local http://localhost:9000 minioadmin minioadmin
```

### Список

```powershell
docker exec dbt_minio mc ls local/dbt-bucket
docker exec dbt_minio mc ls --recursive local/dbt-bucket/stg/suppliers
docker exec dbt_minio mc ls --recursive local/dbt-bucket/retail/stg/orders
docker exec dbt_minio mc ls --recursive local/dbt-bucket/warehouse
```

### Размер

```powershell
docker exec dbt_minio mc du local/dbt-bucket
```

### Удалить префикс (осторожно)

```powershell
docker exec dbt_minio mc rm --recursive --force local/dbt-bucket/retail/stg/orders
```

Генераторы и так чистят свои префиксы при `CLEAN_BEFORE_UPLOAD=true`.

---

## 5. Как данные пишутся

### 5.1. Python-генераторы

Используют `boto3` с:

```python
Config(
    signature_version="s3v4",
    s3={"addressing_style": "path"},
)
```

Path-style обязателен для MinIO.

Каждый CSV загружается через `put_object`:

```
s3://dbt-bucket/{prefix}/{table}/{date}/{table}_part_{n}.csv
```

### 5.2. StarRocks

StarRocks читает CSV через `FILES()`:

```
"s3://dbt-bucket/stg/suppliers/.../suppliers_part_001.csv"
```

Нужны:

- `aws.s3.endpoint=http://minio:9000`;
- `aws.s3.access_key` / `secret_key`;
- `aws.s3.enable_path_style_access=true`;
- `aws.s3.enable_ssl=false`.

### 5.3. Spark / Iceberg

- Spark читает CSV по `s3a://`;
- Iceberg пишет Parquet в `s3://dbt-bucket/warehouse`;
- S3FileIO использует endpoint MinIO.

---

## 6. Проверка данных

```powershell
docker exec dbt_minio mc alias set local http://localhost:9000 minioadmin minioadmin

# bucket существует
docker exec dbt_minio mc ls local/dbt-bucket

# supply chain
docker exec dbt_minio mc ls --recursive local/dbt-bucket/stg/suppliers

# retail
docker exec dbt_minio mc ls --recursive local/dbt-bucket/retail/stg/orders

# Iceberg
docker exec dbt_minio mc ls --recursive local/dbt-bucket/warehouse
```

Ожидаемо: CSV-файлы по датам и Parquet/metadata в warehouse.

---

## 7. Очистка данных

### Только retail

```powershell
docker exec dbt_minio mc rm --recursive --force local/dbt-bucket/retail/stg
```

### Только supply chain

```powershell
docker exec dbt_minio mc rm --recursive --force local/dbt-bucket/stg
```

### Весь bucket (очень осторожно)

```powershell
docker exec dbt_minio mc rm --recursive --force local/dbt-bucket
```

После очистки нужно заново запустить `data-init`/DAG.

---

## 8. Security

- В учебном проекте используются `minioadmin/minioadmin`.
- Для реального проекта:
  - отдельные ключи для генераторов/Spark/StarRocks;
  - ограничение bucket policy;
  - TLS;
  - не хранить секреты в git.
- `.env` с реальными секретами не коммитить. Текущий `.env` — локальный
  учебный.

---

## 9. Частые ошибки

| Ошибка | Причина | Решение |
|---|---|---|
| `Access Denied` у `mc` | alias не настроен/неверные ключи | `mc alias set` |
| `NoSuchBucket` | bucket не создан | генератор создаёт; проверить `mc ls` |
| `SignatureDoesNotMatch` | неверный secret | `.env`/DAG ENV |
| `scheme is null` | virtual-host style | path-style access |
| `SSL error` | MinIO по HTTP | `enable_ssl=false` |
| Файлов нет после генерации | `CLEAN_BEFORE_UPLOAD` + ошибка | смотреть логи `data-init` |
| Дубликаты файлов | не чистятся старые даты | включить очистку prefix |
| `mc` не видит `local` | контейнер пересоздан | alias заново |

---

## 10. Связанные документы

- [`04-data-generation.md`](04-data-generation.md)
- [`05-starrocks.md`](05-starrocks.md)
- [`06-spark-iceberg.md`](06-spark-iceberg.md)
- [`../RUNBOOK.md`](../RUNBOOK.md)
