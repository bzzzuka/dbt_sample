"""
Загрузка retail CSV из MinIO в StarRocks.

Создаёт analytics.raw_retail_* и грузит файлы из retail/stg/{table}/.
"""

import json
import os
import sys
import time
from pathlib import Path

import boto3
import pymysql
from botocore.client import Config


S3_ENDPOINT   = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
S3_ACCESS_KEY = os.getenv("MINIO_ROOT_USER", "minioadmin")
S3_SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
S3_BUCKET     = os.getenv("MINIO_BUCKET", "dbt-bucket")
S3_REGION     = os.getenv("MINIO_REGION", "us-east-1")
PREFIX        = os.getenv("RETAIL_PREFIX", "retail/stg").strip("/")

SR_HOST     = os.getenv("STARROCKS_HOST", "starrocks")
SR_PORT     = int(os.getenv("STARROCKS_PORT", "9030"))
SR_USER     = os.getenv("STARROCKS_USER", "root")
SR_PASSWORD = os.getenv("STARROCKS_PASSWORD", "")
SR_SCHEMA   = os.getenv("STARROCKS_SCHEMA", "analytics")

SCHEMA_JSON_PATH = Path(os.getenv("RETAIL_SCHEMA_JSON_PATH", "/tmp/_retail_schema.json"))


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


def wait_for_starrocks(timeout=240):
    print(f"Ожидание StarRocks ({SR_HOST}:{SR_PORT}), макс {timeout}s...")
    start = time.time()
    attempt = 0
    while time.time() - start < timeout:
        attempt += 1
        try:
            conn = get_sr_conn()
            with conn.cursor() as cur:
                cur.execute("SHOW BACKENDS")
                rows = cur.fetchall()
                cols = [d[0] for d in cur.description]
                alive_idx = cols.index("Alive") if "Alive" in cols else None
                if rows and alive_idx is not None:
                    alive = [r for r in rows if str(r[alive_idx]).lower() == "true"]
                    if alive:
                        print(f"  ✓ StarRocks готов ({len(alive)} BE, попытка {attempt})\n")
                        return conn
            conn.close()
            print(f"  ⏳ попытка {attempt}: FE отвечает, ждём BE...")
        except Exception as e:
            print(f"  ⏳ попытка {attempt}: {type(e).__name__}: {str(e)[:80]}")
        time.sleep(5)
    print("  ❌ StarRocks не поднялся", file=sys.stderr)
    return None


def list_csv_keys(s3, prefix):
    keys = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            if obj["Key"].endswith(".csv"):
                keys.append(obj["Key"])
    return sorted(keys)


def create_tables(conn, schema):
    with conn.cursor() as cur:
        cur.execute(f"CREATE DATABASE IF NOT EXISTS {SR_SCHEMA}")
        cur.execute(f"USE {SR_SCHEMA}")

        for table_name, info in schema.items():
            columns = info["columns"]
            target = f"raw_retail_{table_name}"
            cols_sql = ", ".join(f"`{name}` {sql_type}" for name, sql_type in columns)
            key_col = columns[0][0]

            cur.execute(f"DROP TABLE IF EXISTS {target}")
            cur.execute(f"""
                CREATE TABLE {target} (
                    {cols_sql}
                )
                ENGINE=OLAP
                DUPLICATE KEY(`{key_col}`)
                DISTRIBUTED BY HASH(`{key_col}`) BUCKETS 4
                PROPERTIES ("replication_num" = "1")
            """)
            print(f"  + Таблица {target} создана ({len(columns)} колонок)")


def load_one_file(conn, table_name, s3_key):
    target = f"raw_retail_{table_name}"
    path = f"s3://{S3_BUCKET}/{s3_key}"
    sql = f"""
        INSERT INTO {target}
        SELECT * FROM FILES(
            "path" = "{path}",
            "format" = "csv",
            "csv.column_separator" = ",",
            "csv.row_delimiter" = "\\n",
            "csv.skip_header" = "1",
            "aws.s3.endpoint" = "{S3_ENDPOINT}",
            "aws.s3.access_key" = "{S3_ACCESS_KEY}",
            "aws.s3.secret_key" = "{S3_SECRET_KEY}",
            "aws.s3.region" = "{S3_REGION}",
            "aws.s3.enable_ssl" = "false",
            "aws.s3.enable_path_style_access" = "true"
        )
    """
    with conn.cursor() as cur:
        cur.execute(sql)


def load_table(conn, s3, table_name):
    target = f"raw_retail_{table_name}"
    keys = list_csv_keys(s3, f"{PREFIX}/{table_name}/")
    if not keys:
        print(f"  ⚠ Нет файлов по {PREFIX}/{table_name}/")
        return
    print(f"  ⏳ {target}: {len(keys)} файл(ов)...")
    for key in keys:
        load_one_file(conn, table_name, key)
    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {target}")
        count = cur.fetchone()[0]
    print(f"  ✓ {target}: {count} строк (из {len(keys)} файлов)")


def main():
    print("=" * 60)
    print("  Retail load: MinIO -> StarRocks")
    print("=" * 60)
    print(f"StarRocks: {SR_USER}@{SR_HOST}:{SR_PORT}/{SR_SCHEMA}")
    print(f"S3: {S3_ENDPOINT}, bucket={S3_BUCKET}, prefix={PREFIX}\n")

    if not SCHEMA_JSON_PATH.exists():
        print(f"Схема {SCHEMA_JSON_PATH} не найдена. Сначала запустите generate_retail.py.", file=sys.stderr)
        sys.exit(1)

    schema = json.loads(SCHEMA_JSON_PATH.read_text(encoding="utf-8"))
    print(f"  ✓ Схема загружена: {len(schema)} таблиц\n")

    conn = wait_for_starrocks(timeout=240)
    if not conn:
        sys.exit(1)

    print("Создание таблиц retail...")
    create_tables(conn, schema)
    print()

    print("Загрузка retail-данных из S3...")
    s3 = make_s3_client()
    for table_name in schema:
        load_table(conn, s3, table_name)

    conn.close()
    print("\n✅ Retail загрузка завершена.")


if __name__ == "__main__":
    main()
