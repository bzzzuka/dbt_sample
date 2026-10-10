"""
Читает все CSV из S3 в префиксах stg/{table}/*/*.csv и заливает
в Postgres в таблицы raw_{table}.
"""

import io
import os
import sys
from urllib.parse import urlparse

import boto3
import pandas as pd
from botocore.client import Config
from sqlalchemy import create_engine

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

TABLES = ["customers", "products", "orders", "order_items", "events"]


def make_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY,
        region_name=S3_REGION,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def make_engine():
    url = f"postgresql+psycopg2://{PG_USER}:{PG_PASS}@{PG_HOST}:{PG_PORT}/{PG_DB}"
    return create_engine(url)


def list_csv_keys(s3, prefix: str) -> list[str]:
    keys = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            if obj["Key"].endswith(".csv"):
                keys.append(obj["Key"])
    return sorted(keys)


def read_csv_from_s3(s3, key: str) -> pd.DataFrame:
    body = s3.get_object(Bucket=S3_BUCKET, Key=key)["Body"].read()
    return pd.read_csv(io.BytesIO(body))


def load_table(s3, engine, table: str) -> None:
    prefix = f"{LAYER}/{table}/"
    keys = list_csv_keys(s3, prefix)

    if not keys:
        print(f"  ⚠ Нет файлов по префиксу {prefix} — пропускаю {table}")
        return

    dfs = [read_csv_from_s3(s3, k) for k in keys]
    df = pd.concat(dfs, ignore_index=True)

    target = f"raw_{table}"
    df.to_sql(target, engine, schema="public", if_exists="replace", index=False)
    print(f"  ✓ {target}: {len(df)} строк (из {len(keys)} файлов)")


def main():
    print(f"Чтение из S3: {S3_ENDPOINT}/{S3_BUCKET}, префикс: {LAYER}/*/*/*.csv")
    print(f"Запись в Postgres: {PG_USER}@{PG_HOST}:{PG_PORT}/{PG_DB}\n")

    s3 = make_s3_client()
    engine = make_engine()

    for t in TABLES:
        load_table(s3, engine, t)

    print("\nЗагрузка в Postgres завершена.")


if __name__ == "__main__":
    main()