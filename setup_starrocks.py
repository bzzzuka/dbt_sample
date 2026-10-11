"""
Генератор всех файлов проекта для миграции на StarRocks.

Запуск:
    cd C:\\projects\\dbt_sample
    python setup_starrocks.py

Создаёт/перезаписывает:
  - .env
  - docker-compose.yml
  - dbt/Dockerfile
  - dbt/profiles/profiles.yml
  - dbt/scripts/init.sh
  - dbt/scripts/run_dbt.sh
  - dbt/scripts/load_s3_to_starrocks.py
  - project/models/staging/stg_*.sql  (15 файлов)
  - project/models/staging/sources.yml
  - project/models/marts/mart_*.sql   (6 файлов)
  - project/models/marts/schema.yml
  - project/dbt_project.yml
"""

import os
import sys
from pathlib import Path


# ============ Содержимое файлов ============

FILES = {}

# ---------- .env ----------
FILES[".env"] = """\
# StarRocks
STARROCKS_HOST=starrocks-fe
STARROCKS_PORT=9030
STARROCKS_USER=root
STARROCKS_PASSWORD=
STARROCKS_SCHEMA=analytics
STARROCKS_CATALOG=default_catalog

# MinIO
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin
MINIO_ENDPOINT=http://minio:9000
MINIO_BUCKET=dbt-bucket
MINIO_REGION=us-east-1

# Генерация данных
LAYER=stg
ROWS=5000
CHUNK_SIZE=2500
COLUMNS_PER_TABLE=120
WRITE_LOCAL=false
"""

# ---------- docker-compose.yml ----------
FILES["docker-compose.yml"] = """\
services:

  starrocks-fe:
    image: starrocks/fe-ubuntu:3.4-latest
    container_name: starrocks-fe
    hostname: starrocks-fe
    restart: unless-stopped
    environment:
      - TZ=UTC
      - HOST_TYPE=FQDN
    ports:
      - "8030:8030"
      - "9030:9030"
    volumes:
      - starrocks_fe_meta:/opt/starrocks/fe/meta
      - starrocks_fe_log:/opt/starrocks/fe/log
    command: /opt/starrocks/fe/bin/start_fe.sh
    healthcheck:
      test: ["CMD-SHELL", "mysql -h 127.0.0.1 -P 9030 -uroot -e 'SELECT 1' || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 30
      start_period: 60s
    networks:
      - dbt_network

  starrocks-be:
    image: starrocks/be-ubuntu:3.4-latest
    container_name: starrocks-be
    hostname: starrocks-be
    restart: unless-stopped
    depends_on:
      starrocks-fe:
        condition: service_healthy
    environment:
      - TZ=UTC
      - HOST_TYPE=FQDN
    volumes:
      - starrocks_be_storage:/opt/starrocks/be/storage
      - starrocks_be_log:/opt/starrocks/be/log
    command: /opt/starrocks/be/bin/start_be.sh
    networks:
      - dbt_network

  minio:
    image: ghcr.io/coollabsio/minio:latest
    container_name: dbt_minio
    restart: unless-stopped
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - minio_data:/data
    command: server /data --console-address ":9001"
    healthcheck:
      test: ["CMD", "mc", "ready", "local"]
      interval: 3s
      timeout: 3s
      retries: 20
    networks:
      - dbt_network

  data-init:
    build:
      context: ./dbt
      dockerfile: Dockerfile
    container_name: dbt_data_init
    depends_on:
      starrocks-fe:
        condition: service_healthy
      minio:
        condition: service_healthy
    environment:
      STARROCKS_HOST: ${STARROCKS_HOST}
      STARROCKS_PORT: ${STARROCKS_PORT}
      STARROCKS_USER: ${STARROCKS_USER}
      STARROCKS_PASSWORD: ${STARROCKS_PASSWORD}
      STARROCKS_SCHEMA: ${STARROCKS_SCHEMA}
      STARROCKS_CATALOG: ${STARROCKS_CATALOG}
      MINIO_ENDPOINT: ${MINIO_ENDPOINT}
      MINIO_ROOT_USER: ${MINIO_ROOT_USER}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
      MINIO_BUCKET: ${MINIO_BUCKET}
      MINIO_REGION: ${MINIO_REGION}
      LAYER: ${LAYER}
      ROWS: ${ROWS}
      CHUNK_SIZE: ${CHUNK_SIZE}
      COLUMNS_PER_TABLE: ${COLUMNS_PER_TABLE}
      WRITE_LOCAL: ${WRITE_LOCAL}
    volumes:
      - ./project:/dbt/project
    entrypoint: ["/dbt/scripts/init.sh"]
    networks:
      - dbt_network

  dbt:
    build:
      context: ./dbt
      dockerfile: Dockerfile
    container_name: dbt_runner
    depends_on:
      data-init:
        condition: service_completed_successfully
    environment:
      STARROCKS_HOST: ${STARROCKS_HOST}
      STARROCKS_PORT: ${STARROCKS_PORT}
      STARROCKS_USER: ${STARROCKS_USER}
      STARROCKS_PASSWORD: ${STARROCKS_PASSWORD}
      STARROCKS_SCHEMA: ${STARROCKS_SCHEMA}
      STARROCKS_CATALOG: ${STARROCKS_CATALOG}
    volumes:
      - ./project:/dbt/project
    working_dir: /dbt/project
    entrypoint: ["/dbt/scripts/run_dbt.sh"]
    networks:
      - dbt_network

volumes:
  starrocks_fe_meta:
  starrocks_fe_log:
  starrocks_be_storage:
  starrocks_be_log:
  minio_data:

networks:
  dbt_network:
    driver: bridge
"""

# ---------- dbt/Dockerfile ----------
FILES["dbt/Dockerfile"] = """\
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \\
    git curl default-mysql-client && rm -rf /var/lib/apt/lists/*

WORKDIR /dbt

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --no-cache-dir --upgrade pip && \\
    pip install --no-cache-dir \\
    dbt-core==1.9.0 \\
    dbt-starrocks==1.9.0 \\
    protobuf==4.25.3 \\
    boto3 \\
    pymysql \\
    pandas \\
    requests

COPY profiles/profiles.yml /dbt/profiles/profiles.yml
ENV DBT_PROFILES_DIR=/dbt/profiles

COPY scripts/ /dbt/scripts/
RUN chmod +x /dbt/scripts/*.sh && mkdir -p /dbt/project

CMD ["bash"]
"""

# ---------- dbt/profiles/profiles.yml ----------
FILES["dbt/profiles/profiles.yml"] = """\
default:
  target: dev
  outputs:
    dev:
      type: starrocks
      host: "{{ env_var('STARROCKS_HOST', 'starrocks-fe') }}"
      port: "{{ env_var('STARROCKS_PORT', '9030') | int }}"
      schema: "{{ env_var('STARROCKS_SCHEMA', 'analytics') }}"
      username: "{{ env_var('STARROCKS_USER', 'root') }}"
      password: "{{ env_var('STARROCKS_PASSWORD', '') }}"
      catalog: "{{ env_var('STARROCKS_CATALOG', 'default_catalog') }}"
      version: "3.4.0"
"""

# ---------- dbt/scripts/init.sh ----------
FILES["dbt/scripts/init.sh"] = """\
#!/usr/bin/env bash
set -euo pipefail

echo "============================================================"
echo "  data-init: генерация → S3 → StarRocks"
echo "============================================================"

echo
echo ">>> [1/2] Генерация данных и загрузка в MinIO (S3)"
python /dbt/scripts/generate_and_upload.py

echo
echo ">>> [2/2] Загрузка данных из MinIO (S3) в StarRocks"
python /dbt/scripts/load_s3_to_starrocks.py

echo
echo "============================================================"
echo "  data-init: готово"
echo "============================================================"
"""

# ---------- dbt/scripts/run_dbt.sh ----------
FILES["dbt/scripts/run_dbt.sh"] = """\
#!/usr/bin/env bash
set -euo pipefail

echo "============================================================"
echo "  dbt: запуск моделей"
echo "============================================================"

cd /dbt/project

dbt debug
dbt run
dbt test

echo
echo "============================================================"
echo "  dbt: успешно завершено"
echo "============================================================"
"""

# ---------- dbt/scripts/load_s3_to_starrocks.py ----------
FILES["dbt/scripts/load_s3_to_starrocks.py"] = """\
\"\"\"
Загружает CSV из MinIO (S3) в StarRocks.

Использует INSERT INTO ... FILES() для прямой загрузки из S3.
Требует StarRocks v3.3+.
\"\"\"

import json
import os
import sys
from pathlib import Path

import boto3
import pymysql
from botocore.client import Config


S3_ENDPOINT   = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
S3_ACCESS_KEY = os.getenv("MINIO_ROOT_USER", "minioadmin")
S3_SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
S3_BUCKET     = os.getenv("MINIO_BUCKET", "dbt-bucket")
S3_REGION     = os.getenv("MINIO_REGION", "us-east-1")
LAYER         = os.getenv("LAYER", "stg")

SR_HOST     = os.getenv("STARROCKS_HOST", "starrocks-fe")
SR_PORT     = int(os.getenv("STARROCKS_PORT", "9030"))
SR_USER     = os.getenv("STARROCKS_USER", "root")
SR_PASSWORD = os.getenv("STARROCKS_PASSWORD", "")
SR_SCHEMA   = os.getenv("STARROCKS_SCHEMA", "analytics")

SCHEMA_JSON_PATH = Path(os.getenv("SCHEMA_JSON_PATH", "/dbt/_schema.json"))


KIND_TO_SR = {
    "code": "VARCHAR(255)", "date": "DATE", "datetime": "DATETIME",
    "money": "DECIMAL(15,2)", "int": "INT", "float": "DECIMAL(15,3)",
    "name": "VARCHAR(255)", "product": "VARCHAR(255)", "category": "VARCHAR(255)",
    "subcategory": "VARCHAR(255)", "brand": "VARCHAR(255)", "model": "VARCHAR(255)",
    "country": "VARCHAR(10)", "city": "VARCHAR(100)", "region": "VARCHAR(100)",
    "bool": "BOOLEAN", "coord": "DECIMAL(10,6)",
    "text": "VARCHAR(1000)", "email": "VARCHAR(255)", "phone": "VARCHAR(50)",
    "url": "VARCHAR(500)", "direction": "VARCHAR(50)",
}
for _e in ["incoterms","payment_terms","currency","uom","status","payment_status",
           "shipment_type","transport_mode","container_type","priority",
           "quality_grade","hazard_class","packaging_type","loading_type",
           "customs_regime","delivery_terms"]:
    KIND_TO_SR[_e] = "VARCHAR(50)"


def make_s3_client():
    return boto3.client(
        "s3", endpoint_url=S3_ENDPOINT,
        aws_access_key_id=S3_ACCESS_KEY, aws_secret_access_key=S3_SECRET_KEY,
        region_name=S3_REGION,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def get_sr_conn():
    return pymysql.connect(
        host=SR_HOST, port=SR_PORT, user=SR_USER,
        password=SR_PASSWORD, charset="utf8mb4", autocommit=True,
    )


def list_csv_keys(s3, prefix):
    keys = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            if obj["Key"].endswith(".csv"):
                keys.append(obj["Key"])
    return sorted(keys)


def create_schema_and_tables(conn, schema):
    with conn.cursor() as cur:
        cur.execute(f"CREATE DATABASE IF NOT EXISTS {SR_SCHEMA}")
        cur.execute(f"USE {SR_SCHEMA}")

        for table_name, info in schema.items():
            cols = info["columns"]
            target = f"raw_{table_name}"
            cols_sql = ", ".join(f"`{c}` {KIND_TO_SR.get(t, 'VARCHAR(255)')}" for c, t in cols)
            key_cols = [c for c, _ in cols][:3]
            keys_sql = ", ".join(f"`{c}`" for c in key_cols)

            cur.execute(f"DROP TABLE IF EXISTS {target}")
            cur.execute(f\"\"\"
                CREATE TABLE {target} (
                    {cols_sql}
                )
                ENGINE=OLAP
                DUPLICATE KEY({keys_sql})
                DISTRIBUTED BY HASH(`{key_cols[0]}`) BUCKETS 4
                PROPERTIES ("replication_num" = "1")
            \"\"\")
            print(f"  + Таблица {target} создана ({len(cols)} колонок)")


def load_table_from_s3(conn, table_name):
    target = f"raw_{table_name}"
    path_pattern = f"{S3_BUCKET}/{LAYER}/{table_name}/*/*.csv"

    sql = f\"\"\"
        INSERT INTO {target}
        SELECT * FROM FILES(
            "path" = "{path_pattern}",
            "format" = "csv",
            "csv.column_separator" = ",",
            "csv.row_delimiter" = "\\\\n",
            "csv.skip_header" = "1",
            "aws.s3.endpoint" = "{S3_ENDPOINT}",
            "aws.s3.access_key" = "{S3_ACCESS_KEY}",
            "aws.s3.secret_key" = "{S3_SECRET_KEY}",
            "aws.s3.region" = "{S3_REGION}",
            "aws.s3.enable_path_style_access" = "true"
        )
    \"\"\"

    with conn.cursor() as cur:
        cur.execute(sql)
        cur.execute(f"SELECT COUNT(*) FROM {target}")
        count = cur.fetchone()[0]

    print(f"  ✓ {target}: {count} строк загружено")


def main():
    print(f"StarRocks: {SR_USER}@{SR_HOST}:{SR_PORT}/{SR_SCHEMA}")
    print(f"S3: {S3_ENDPOINT}, bucket={S3_BUCKET}, layer={LAYER}\\n")

    if not SCHEMA_JSON_PATH.exists():
        print(f"Схема {SCHEMA_JSON_PATH} не найдена. Сначала запустите генератор.", file=sys.stderr)
        sys.exit(1)

    schema = json.loads(SCHEMA_JSON_PATH.read_text(encoding="utf-8"))
    print(f"  ✓ Схема загружена: {len(schema)} таблиц\\n")

    print("Подключение к StarRocks...")
    conn = get_sr_conn()
    print("  ✓ Подключено\\n")

    print("Создание схемы и таблиц...")
    create_schema_and_tables(conn, schema)
    print()

    print("Загрузка данных из S3 в StarRocks...")
    for table_name in sorted(schema.keys()):
        try:
            load_table_from_s3(conn, table_name)
        except Exception as e:
            print(f"  ❌ Ошибка загрузки {table_name}: {e}")
            raise

    conn.close()
    print("\\n✅ Загрузка в StarRocks завершена.")


if __name__ == "__main__":
    main()
"""

# ---------- project/dbt_project.yml ----------
FILES["project/dbt_project.yml"] = """\
name: 'my_dbt_project'
version: '1.0.0'
config-version: 2

profile: 'default'

model-paths: ["models"]
target-path: "target"
clean-targets: ["target", "dbt_packages"]

models:
  my_dbt_project:
    staging:
      +materialized: view
    marts:
      +materialized: table
"""

# ---------- project/models/staging/sources.yml ----------
STG_TABLES = [
    "suppliers", "supply_contracts", "supply_orders", "supply_items",
    "shipments", "warehouses", "deliveries", "invoices", "payments",
    "quality_checks", "returns", "inventory_movements", "transport_routes",
    "customs_declarations", "supplier_ratings",
]

sources_lines = ["version: 2", "", "sources:", "  - name: raw",
                 "    schema: analytics", "    tables:"]
for t in STG_TABLES:
    sources_lines.append(f"      - name: raw_{t}")
FILES["project/models/staging/sources.yml"] = "\n".join(sources_lines) + "\n"

# ---------- project/models/staging/stg_*.sql ----------
for t in STG_TABLES:
    FILES[f"project/models/staging/stg_{t}.sql"] = (
        "{{ config(materialized='view') }}\n\n"
        f"SELECT * FROM {{{{ source('raw', 'raw_{t}') }}}}\n"
    )

# ---------- project/models/marts/*.sql ----------
FILES["project/models/marts/mart_supplier_performance.sql"] = """\
{{ config(
    materialized='table',
    engine='OLAP',
    keys=['supplier_id'],
    table_type='PRIMARY',
    distributed_by=['supplier_id'],
    buckets=4,
    properties={"replication_num": "1"}
) }}

WITH supplier_orders AS (
    SELECT
        o.supplier_id,
        COUNT(*)              AS orders_count,
        SUM(o.total_price)    AS total_purchase_amount,
        AVG(o.total_price)    AS avg_order_amount,
        MIN(o.order_date)     AS first_order_date,
        MAX(o.order_date)     AS last_order_date
    FROM {{ ref('stg_supply_orders') }} o
    GROUP BY o.supplier_id
),
supplier_contracts AS (
    SELECT
        supplier_id,
        COUNT(*)           AS contracts_count,
        SUM(total_price)   AS contracts_total_amount
    FROM {{ ref('stg_supply_contracts') }}
    GROUP BY supplier_id
),
supplier_quality AS (
    SELECT
        s.supplier_id,
        AVG(sr.rating) AS avg_rating,
        COUNT(*)       AS ratings_count
    FROM {{ ref('stg_supplier_ratings') }} sr
    JOIN {{ ref('stg_suppliers') }} s ON s.supplier_id = sr.supplier_id
    GROUP BY s.supplier_id
)
SELECT
    s.supplier_id,
    s.supplier_name,
    s.country,
    s.city,
    s.region,
    s.rating                                  AS current_rating,
    COALESCE(sc.contracts_count, 0)           AS contracts_count,
    COALESCE(sc.contracts_total_amount, 0)    AS contracts_total_amount,
    COALESCE(so.orders_count, 0)              AS orders_count,
    COALESCE(so.total_purchase_amount, 0)     AS total_purchase_amount,
    COALESCE(so.avg_order_amount, 0)          AS avg_order_amount,
    so.first_order_date,
    so.last_order_date,
    COALESCE(sq.avg_rating, 0)                AS avg_quality_rating,
    COALESCE(sq.ratings_count, 0)             AS ratings_count
FROM {{ ref('stg_suppliers') }} s
LEFT JOIN supplier_contracts sc USING (supplier_id)
LEFT JOIN supplier_orders    so USING (supplier_id)
LEFT JOIN supplier_quality   sq USING (supplier_id)
"""

FILES["project/models/marts/mart_supply_by_category.sql"] = """\
{{ config(
    materialized='table',
    engine='OLAP',
    keys=['category'],
    table_type='PRIMARY',
    distributed_by=['category'],
    buckets=4,
    properties={"replication_num": "1"}
) }}

SELECT
    i.category,
    COUNT(DISTINCT i.supply_order_id)          AS orders_count,
    COUNT(*)                                   AS items_count,
    SUM(i.quantity)                            AS total_quantity,
    SUM(i.total_price)                         AS total_revenue,
    AVG(i.unit_price)                          AS avg_unit_price,
    COUNT(DISTINCT i.unit_of_measure)          AS uom_variety
FROM {{ ref('stg_supply_items') }} i
GROUP BY i.category
ORDER BY total_revenue DESC
"""

FILES["project/models/marts/mart_delivery_kpi.sql"] = """\
{{ config(
    materialized='table',
    engine='OLAP',
    keys=['transport_mode', 'container_type', 'priority'],
    table_type='PRIMARY',
    distributed_by=['transport_mode'],
    buckets=4,
    properties={"replication_num": "1"}
) }}

WITH shipments AS (
    SELECT
        s.shipment_id,
        s.supply_order_id,
        s.ship_date,
        s.delivery_date,
        s.transport_mode,
        s.container_type,
        s.weight_kg,
        s.shipping_cost,
        s.status,
        DATEDIFF(s.delivery_date, s.ship_date) AS delivery_days,
        o.priority
    FROM {{ ref('stg_shipments') }} s
    LEFT JOIN {{ ref('stg_supply_orders') }} o USING (supply_order_id)
)
SELECT
    transport_mode,
    container_type,
    priority,
    COUNT(*)                                        AS shipments_count,
    SUM(weight_kg)                                  AS total_weight_kg,
    SUM(shipping_cost)                              AS total_shipping_cost,
    AVG(shipping_cost)                              AS avg_shipping_cost,
    AVG(delivery_days)                              AS avg_delivery_days,
    MIN(delivery_days)                              AS min_delivery_days,
    MAX(delivery_days)                              AS max_delivery_days,
    COUNT(CASE WHEN status = 'delivered' THEN 1 END) AS delivered_count,
    COUNT(CASE WHEN status = 'cancelled' THEN 1 END) AS cancelled_count,
    COUNT(CASE WHEN status = 'returned' THEN 1 END)  AS returned_count
FROM shipments
GROUP BY transport_mode, container_type, priority
"""

FILES["project/models/marts/mart_warehouse_activity.sql"] = """\
{{ config(
    materialized='table',
    engine='OLAP',
    keys=['warehouse_id'],
    table_type='PRIMARY',
    distributed_by=['warehouse_id'],
    buckets=4,
    properties={"replication_num": "1"}
) }}

WITH movements AS (
    SELECT
        warehouse_id,
        COUNT(*)                                        AS movements_count,
        SUM(quantity)                                   AS total_quantity,
        COUNT(CASE WHEN direction = 'in' THEN 1 END)     AS inbound_count,
        COUNT(CASE WHEN direction = 'out' THEN 1 END)    AS outbound_count,
        MIN(movement_date)                              AS first_movement,
        MAX(movement_date)                              AS last_movement
    FROM {{ ref('stg_inventory_movements') }}
    GROUP BY warehouse_id
),
deliveries AS (
    SELECT
        warehouse_id,
        COUNT(*)                                        AS deliveries_count,
        COUNT(CASE WHEN status = 'delivered' THEN 1 END) AS delivered_count,
        COUNT(CASE WHEN status = 'returned' THEN 1 END)  AS returned_count
    FROM {{ ref('stg_deliveries') }}
    GROUP BY warehouse_id
)
SELECT
    w.warehouse_id,
    w.warehouse_name,
    w.city,
    w.country,
    w.capacity_m3,
    COALESCE(m.movements_count, 0)    AS movements_count,
    COALESCE(m.total_quantity, 0)     AS total_quantity_moved,
    COALESCE(m.inbound_count, 0)      AS inbound_count,
    COALESCE(m.outbound_count, 0)     AS outbound_count,
    COALESCE(d.deliveries_count, 0)   AS deliveries_count,
    COALESCE(d.delivered_count, 0)    AS delivered_count,
    COALESCE(d.returned_count, 0)     AS returned_count,
    m.first_movement,
    m.last_movement
FROM {{ ref('stg_warehouses') }} w
LEFT JOIN movements  m USING (warehouse_id)
LEFT JOIN deliveries d USING (warehouse_id)
"""

FILES["project/models/marts/mart_payment_summary.sql"] = """\
{{ config(
    materialized='table',
    engine='OLAP',
    keys=['month', 'currency'],
    table_type='PRIMARY',
    distributed_by=['month'],
    buckets=4,
    properties={"replication_num": "1"}
) }}

WITH invoices AS (
    SELECT
        DATE_FORMAT(invoice_date, '%Y-%m-01')  AS invoice_month,
        currency,
        payment_status,
        COUNT(*)                                AS invoices_count,
        SUM(total_price)                        AS invoices_total
    FROM {{ ref('stg_invoices') }}
    GROUP BY 1, 2, 3
),
payments AS (
    SELECT
        DATE_FORMAT(payment_date, '%Y-%m-01')  AS payment_month,
        currency,
        payment_status,
        COUNT(*)                                AS payments_count,
        SUM(total_price)                        AS payments_total
    FROM {{ ref('stg_payments') }}
    GROUP BY 1, 2, 3
)
SELECT
    COALESCE(i.invoice_month, p.payment_month) AS month,
    COALESCE(i.currency, p.currency)           AS currency,
    COALESCE(i.invoices_count, 0)              AS invoices_count,
    COALESCE(i.invoices_total, 0)              AS invoices_total,
    COALESCE(p.payments_count, 0)              AS payments_count,
    COALESCE(p.payments_total, 0)              AS payments_total,
    CASE
        WHEN COALESCE(i.invoices_total, 0) > 0
        THEN ROUND(COALESCE(p.payments_total, 0) / i.invoices_total * 100, 2)
        ELSE NULL
    END                                        AS payment_ratio_pct
FROM invoices i
FULL OUTER JOIN payments p
    ON i.invoice_month = p.payment_month
   AND i.currency = p.currency
"""

FILES["project/models/marts/mart_transport_analysis.sql"] = """\
{{ config(
    materialized='table',
    engine='OLAP',
    keys=['transport_mode'],
    table_type='PRIMARY',
    distributed_by=['transport_mode'],
    buckets=4,
    properties={"replication_num": "1"}
) }}

WITH routes AS (
    SELECT
        transport_mode,
        COUNT(*)             AS routes_count,
        SUM(distance_km)     AS total_distance_km,
        AVG(distance_km)     AS avg_distance_km,
        MIN(distance_km)     AS min_distance_km,
        MAX(distance_km)     AS max_distance_km
    FROM {{ ref('stg_transport_routes') }}
    GROUP BY transport_mode
),
shipments AS (
    SELECT
        transport_mode,
        COUNT(*)             AS shipments_count,
        SUM(shipping_cost)   AS total_shipping_cost,
        AVG(shipping_cost)   AS avg_shipping_cost,
        SUM(weight_kg)       AS total_weight_kg
    FROM {{ ref('stg_shipments') }}
    GROUP BY transport_mode
)
SELECT
    COALESCE(r.transport_mode, s.transport_mode) AS transport_mode,
    COALESCE(r.routes_count, 0)                  AS routes_count,
    COALESCE(r.total_distance_km, 0)             AS total_distance_km,
    COALESCE(r.avg_distance_km, 0)               AS avg_distance_km,
    COALESCE(s.shipments_count, 0)               AS shipments_count,
    COALESCE(s.total_shipping_cost, 0)           AS total_shipping_cost,
    COALESCE(s.avg_shipping_cost, 0)             AS avg_shipping_cost,
    COALESCE(s.total_weight_kg, 0)               AS total_weight_kg,
    CASE
        WHEN COALESCE(r.total_distance_km, 0) > 0
        THEN ROUND(COALESCE(s.total_shipping_cost, 0) / r.total_distance_km, 4)
        ELSE NULL
    END                                          AS cost_per_km
FROM routes r
FULL OUTER JOIN shipments s USING (transport_mode)
"""

FILES["project/models/marts/schema.yml"] = """\
version: 2

models:
  - name: mart_supplier_performance
    description: "KPI по каждому поставщику: контракты, заказы, суммы, рейтинг."
    columns:
      - name: supplier_id
        tests: [unique, not_null]
      - name: supplier_name
        tests: [not_null]

  - name: mart_supply_by_category
    description: "Агрегаты поставок по категориям товаров."
    columns:
      - name: category
        tests: [unique, not_null]

  - name: mart_delivery_kpi
    description: "KPI доставок: сроки, стоимость, статусы по модальностям."

  - name: mart_warehouse_activity
    description: "Активность складов: движения, доставки, возвраты."
    columns:
      - name: warehouse_id
        tests: [unique, not_null]

  - name: mart_payment_summary
    description: "Сводка по платежам и инвойсам по месяцам и валютам."

  - name: mart_transport_analysis
    description: "Анализ маршрутов и стоимости доставки по видам транспорта."
    columns:
      - name: transport_mode
        tests: [unique, not_null]
"""


# ============ Основная логика ============

def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # UTF-8 без BOM, LF-переводы строк
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print(f"  OK: {path}")


def main():
    project_root = Path.cwd()
    print(f"Корень проекта: {project_root}\n")

    # Проверка, что запускаем из корня проекта
    if not (project_root / "project").exists() and not (project_root / "dbt").exists():
        print("⚠ Запустите скрипт из корня проекта (там, где лежит docker-compose.yml)", file=sys.stderr)
        print("  Например: cd C:\\projects\\dbt_sample", file=sys.stderr)
        sys.exit(1)

    print("Создание файлов...\n")
    for rel_path, content in FILES.items():
        write_file(project_root / rel_path, content)

    # chmod +x для shell-скриптов (актуально внутри контейнера, но не помешает)
    for sh in ["dbt/scripts/init.sh", "dbt/scripts/run_dbt.sh"]:
        p = project_root / sh
        if p.exists():
            try:
                os.chmod(p, 0o755)
            except Exception:
                pass  # на Windows chmod может не сработать — не критично

    print(f"\n✅ Готово! Создано {len(FILES)} файлов.")
    print("\nДальше:")
    print("  docker compose down -v")
    print("  docker compose up --build")


if __name__ == "__main__":
    main()