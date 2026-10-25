"""
Загрузка исторических цен акций с Московской биржи (MOEX ISS API) в MinIO.
"""
import csv
import io
import os
import sys
import time
from datetime import datetime, timedelta

try:
    import boto3
    import requests
    from botocore.client import Config
except ImportError:
    print("Требуется boto3 и requests", file=sys.stderr)
    sys.exit(1)

TICKERS = os.getenv("MOEX_TICKERS", "SBER,GAZP,LKOH,VTBR,AFLT").split(",")
FROM_DATE = os.getenv("MOEX_FROM", (datetime.utcnow() - timedelta(days=365)).strftime("%Y-%m-%d"))
TO_DATE = os.getenv("MOEX_TO", datetime.utcnow().strftime("%Y-%m-%d"))
BOARD = os.getenv("MOEX_BOARD", "TQBR")
PARTITION_DATE = os.getenv("PARTITION_DATE", datetime.utcnow().strftime("%Y-%m-%d"))

S3_ENDPOINT   = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
S3_ACCESS_KEY = os.getenv("MINIO_ROOT_USER", "minioadmin")
S3_SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
S3_BUCKET     = os.getenv("MINIO_BUCKET", "dbt-bucket")
S3_REGION     = os.getenv("MINIO_REGION", "us-east-1")
LAYER         = os.getenv("LAYER", "stg")
TABLE_NAME    = "moex_prices"

MOEX_BASE = "https://iss.moex.com/iss/history/engines/stock/markets/shares/boards"
HEADERS = {"User-Agent": "dbt-sample-project/1.0"}


def make_s3_client():
    return boto3.client(
        "s3", endpoint_url=S3_ENDPOINT,
        aws_access_key_id=S3_ACCESS_KEY, aws_secret_access_key=S3_SECRET_KEY,
        region_name=S3_REGION,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def fetch_moex_history(ticker, from_date, to_date, board):
    url = f"{MOEX_BASE}/{board}/securities/{ticker}.json"
    params = {"from": from_date, "till": to_date, "iss.meta": "off", "iss.only": "history"}
    all_rows = []
    start = 0
    while True:
        params["start"] = start
        try:
            resp = requests.get(url, params=params, headers=HEADERS, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"  ❌ {ticker}: {e}", file=sys.stderr)
            return []
        data = resp.json()
        history = data.get("history", {})
        columns = history.get("columns", [])
        rows = history.get("data", [])
        if not rows:
            break
        for row in rows:
            record = dict(zip(columns, row))
            tradedate = record.get("TRADEDATE")
            if not tradedate:
                continue
            close_price = record.get("LEGALCLOSEPRICE") or record.get("CLOSE")
            all_rows.append({
                "ticker": ticker,
                "tradedate": tradedate,
                "open": record.get("OPEN"),
                "high": record.get("HIGH"),
                "low": record.get("LOW"),
                "close": close_price,
                "volume": record.get("VOLUME"),
                "value": record.get("VALUE"),
                "numtrades": record.get("NUMTRADES"),
                "boardid": record.get("BOARDID"),
            })
        start += len(rows)
        if len(rows) < 100:
            break
        time.sleep(0.1)
    return all_rows


def rows_to_csv_bytes(rows, columns):
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns)
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")


def main():
    print(f"MOEX -> MinIO")
    print(f"  Тикеры: {', '.join(TICKERS)}")
    print(f"  Период: {FROM_DATE} — {TO_DATE}")
    print(f"  Board: {BOARD}")
    print(f"  S3: {S3_ENDPOINT}, bucket={S3_BUCKET}, partition={PARTITION_DATE}\n")

    all_rows = []
    for ticker in TICKERS:
        ticker = ticker.strip()
        print(f">>> {ticker}")
        rows = fetch_moex_history(ticker, FROM_DATE, TO_DATE, BOARD)
        print(f"  ✓ {len(rows)} строк")
        all_rows.extend(rows)

    if not all_rows:
        print("\n❌ Нет данных", file=sys.stderr)
        sys.exit(1)

    all_rows.sort(key=lambda r: (r["ticker"], r["tradedate"]))
    columns = ["ticker", "tradedate", "open", "high", "low", "close",
               "volume", "value", "numtrades", "boardid"]

    payload = rows_to_csv_bytes(all_rows, columns)
    key = f"{LAYER}/{TABLE_NAME}/{PARTITION_DATE}/{TABLE_NAME}_part_001.csv"

    s3 = make_s3_client()
    s3.put_object(Bucket=S3_BUCKET, Key=key, Body=payload, ContentType="text/csv")
    print(f"\n  ✓ s3://{S3_BUCKET}/{key} ({len(all_rows)} строк, {len(payload)/1024:.1f} KB)")
    print(f"\n✅ Готово. {len(all_rows)} строк загружено в MinIO.")


if __name__ == "__main__":
    main()
