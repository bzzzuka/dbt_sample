"""
Читает все CSV из S3 по префиксам stg/{table}/*/*.csv
и заливает в Postgres как raw_{table}.

Типы колонок берутся из /dbt/_schema.json, который пишет генератор.
"""

import io
import json
import os
import sys
from pathlib import Path

import boto3
import pandas as pd
import psycopg2
from botocore.client import Config


S3_ENDPOINT   = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
S3_ACCESS_KEY = os.getenv("MINIO_ROOT_USER", "minioadmin")
S3_SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
S3_BUCKET     = os.getenv("MINIO_BUCKET", "dbt-bucket")
S3_REGION     = os.getenv("MINIO_REGION", "us-east-1")
LAYER         = os.getenv("LAYER", "stg")

PG_HOST = os.getenv("POSTGRES_HOST", "postgres")
PG_PORT = os.getenv("POSTGRES_PORT", "5432")
PG_USER = os.getenv("POSTGRES_USER", "dbt_user")
PG_PASS = os.getenv("POSTGRES_PASSWORD", "dbt_password")
PG_DB   = os.getenv("POSTGRES_DB", "dbt_db")

SCHEMA_JSON_PATH = Path(os.getenv("SCHEMA_JSON_PATH", "/dbt/_schema.json"))


def make_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY,
        region_name=S3_REGION,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def get_conn():
    return psycopg2.connect(
        host=PG_HOST, port=PG_PORT, user=PG_USER,
        password=PG_PASS, dbname=PG_DB,
    )


def list_csv_keys(s3, prefix):
    keys = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            if obj["Key"].endswith(".csv"):
                keys.append(obj["Key"])
    return sorted(keys)


def read_csv_from_s3(s3, key):
    body = s3.get_object(Bucket=S3_BUCKET, Key=key)["Body"].read()
    return pd.read_csv(io.BytesIO(body))


def discover_tables(s3):
    tables = set()
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=f"{LAYER}/", Delimiter="/"):
        for prefix in page.get("CommonPrefixes", []):
            name = prefix["Prefix"].rstrip("/").split("/")[-1]
            tables.add(name)
    return sorted(tables)


def load_table(s3, conn, table_name, schema_columns):
    prefix = f"{LAYER}/{table_name}/"
    keys = list_csv_keys(s3, prefix)
    if not keys:
        print(f"  ⚠ Нет файлов по {prefix} — пропускаю")
        return

    dfs = [read_csv_from_s3(s3, k) for k in keys]
    df = pd.concat(dfs, ignore_index=True)

    # если нет схемы — все колонки как TEXT
    if schema_columns is None:
        schema_columns = [(c, "TEXT") for c in df.columns]

    # ЗАЩИТА: приводим порядок колонок DataFrame к порядку из схемы.
    # Если какого-то столбца нет — добавим его как NULL.
    expected_cols = [c for c, _ in schema_columns]
    for col in expected_cols:
        if col not in df.columns:
            df[col] = None
    df = df[expected_cols]

    target = f"raw_{table_name}"
    cols_sql = ", ".join(f'"{c}" {t}' for c, t in schema_columns)
    cols_list = ", ".join(f'"{c}"' for c in expected_cols)

    with conn.cursor() as cur:
        cur.execute(f'DROP TABLE IF EXISTS public."{target}" CASCADE')
        cur.execute(f'CREATE TABLE public."{target}" ({cols_sql})')
    conn.commit()

    buf = io.StringIO()
    df.to_csv(buf, index=False, header=False)
    buf.seek(0)
    with conn.cursor() as cur:
        cur.copy_expert(
            f'COPY public."{target}" ({cols_list}) FROM STDIN WITH (FORMAT CSV, NULL \'\')',
            buf,
        )
    conn.commit()

    print(f"  ✓ {target}: {len(df)} строк, {len(schema_columns)} колонок (из {len(keys)} файлов)")


def main():
    print(f"Чтение из S3: {S3_ENDPOINT}/{S3_BUCKET}, префикс: {LAYER}/*/*/*.csv")
    print(f"Запись в Postgres: {PG_USER}@{PG_HOST}:{PG_PORT}/{PG_DB}\n")

    s3 = make_s3_client()
    conn = get_conn()

    schema = {}
    if SCHEMA_JSON_PATH.exists():
        schema = json.loads(SCHEMA_JSON_PATH.read_text(encoding="utf-8"))
        print(f"  ✓ Схема загружена: {len(schema)} таблиц\n")
    else:
        print(f"  ⚠ Схема {SCHEMA_JSON_PATH} не найдена, читаю типы из CSV\n")

    tables = sorted(schema.keys()) if schema else discover_tables(s3)

    for table_name in tables:
        cols = schema[table_name]["columns"] if table_name in schema else None
        load_table(s3, conn, table_name, cols)

    conn.close()
    print("\n✅ Загрузка в Postgres завершена.")


if __name__ == "__main__":
    main()