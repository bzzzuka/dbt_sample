"""
Генерация 5 CSV-таблиц (связных) + загрузка в MinIO (S3).

Структура в бакете:
    stg/customers/{YYYY-MM-DD}/customers_part_001.csv
    stg/products/{YYYY-MM-DD}/products_part_001.csv
    stg/orders/{YYYY-MM-DD}/orders_part_001.csv
    stg/order_items/{YYYY-MM-DD}/order_items_part_001.csv
    stg/events/{YYYY-MM-DD}/events_part_001.csv
"""

import csv
import io
import os
import random
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

try:
    import boto3
    from botocore.client import Config
    from botocore.exceptions import ClientError
except ImportError:
    print("Нужен boto3", file=sys.stderr)
    sys.exit(1)


# --- Настройки ---
ROWS        = int(os.getenv("ROWS", "10000"))
CHUNK_SIZE  = int(os.getenv("CHUNK_SIZE", "5000"))
RANDOM_SEED = int(os.getenv("RANDOM_SEED", "42"))

S3_ENDPOINT   = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
S3_ACCESS_KEY = os.getenv("MINIO_ROOT_USER", "minioadmin")
S3_SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
S3_BUCKET     = os.getenv("MINIO_BUCKET", "dbt-bucket")
S3_REGION     = os.getenv("MINIO_REGION", "us-east-1")
LAYER         = os.getenv("LAYER", "stg")

WRITE_LOCAL = os.getenv("WRITE_LOCAL", "false").lower() in ("1", "true", "yes")
LOCAL_DIR   = Path(os.getenv("LOCAL_DIR", "./data"))
PARTITION_DATE = os.getenv("PARTITION_DATE", datetime.utcnow().strftime("%Y-%m-%d"))

random.seed(RANDOM_SEED)

# --- Справочники ---
FIRST_NAMES = ["Иван","Пётр","Сергей","Алексей","Дмитрий","Андрей","Михаил",
               "Николай","Владимир","Егор","Мария","Анна","Елена","Ольга",
               "Татьяна","Наталья","Ирина","Светлана","Юлия","Екатерина"]
LAST_NAMES = ["Иванов","Петров","Сидоров","Смирнов","Кузнецов","Попов",
              "Васильев","Соколов","Михайлов","Новиков","Фёдоров","Морозов",
              "Волков","Алексеев","Лебедев","Семёнов","Егоров","Павлов"]
CITIES = ["Москва","Санкт-Петербург","Новосибирск","Екатеринбург","Казань",
          "Нижний Новгород","Челябинск","Самара","Омск","Ростов-на-Дону",
          "Уфа","Красноярск","Воронеж","Пермь","Волгоград"]
COUNTRIES = ["RU","KZ","BY","UA"]

CATEGORIES = {
    "Electronics": ["Смартфон","Ноутбук","Наушники","Планшет","Монитор","Клавиатура","Мышь"],
    "Home":        ["Чайник","Пылесос","Микроволновка","Утюг","Кофемашина","Блендер"],
    "Books":       ["Роман","Учебник","Детектив","Фантастика","Биография","Поэзия"],
    "Clothing":    ["Футболка","Джинсы","Куртка","Кроссовки","Свитер","Шапка"],
    "Sports":      ["Велосипед","Гантели","Коврик для йоги","Скакалка","Мяч","Турник"],
}
BRANDS = ["BrandA","BrandB","BrandC","BrandD","BrandE","NoName"]

ORDER_STATUSES  = ["created","paid","shipped","delivered","cancelled","returned"]
PAYMENT_METHODS = ["card","cash","sbp","wallet"]
EVENT_TYPES     = ["page_view","product_view","add_to_cart","remove_from_cart","checkout","search"]
DEVICES         = ["desktop","mobile","tablet"]
CHANNELS        = ["organic","ads","email","social","referral","direct"]


def random_datetime(start_days_ago: int = 365) -> datetime:
    now = datetime.utcnow()
    return now - timedelta(
        days=random.randint(0, start_days_ago),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
        seconds=random.randint(0, 59),
    )

def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def rows_to_csv_bytes(rows: list[dict]) -> bytes:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue().encode("utf-8")

def chunked(seq: list, size: int):
    for i in range(0, len(seq), size):
        yield i // size + 1, seq[i:i + size]


# --- Генераторы ---
def gen_customers(n):
    rows = []
    for i in range(1, n + 1):
        rows.append({
            "customer_id": i,
            "first_name": random.choice(FIRST_NAMES),
            "last_name": random.choice(LAST_NAMES),
            "email": f"user{i}@{random.choice(['mail.ru','gmail.com','yandex.ru','bk.ru'])}",
            "phone": f"+7{random.randint(900_000_0000, 999_999_9999)}",
            "city": random.choice(CITIES),
            "country": random.choice(COUNTRIES),
            "created_at": iso(random_datetime(730)),
            "is_active": random.choice([True, False]),
        })
    return rows

def gen_products(n):
    rows = []
    for i in range(1, n + 1):
        cat = random.choice(list(CATEGORIES.keys()))
        sub = random.choice(CATEGORIES[cat])
        price = round(random.uniform(99, 99999), 2)
        rows.append({
            "product_id": i,
            "sku": f"SKU-{i:06d}",
            "name": f"{sub} #{i}",
            "category": cat,
            "subcategory": sub,
            "brand": random.choice(BRANDS),
            "price": price,
            "cost": round(price * random.uniform(0.4, 0.8), 2),
            "stock_quantity": random.randint(0, 500),
            "created_at": iso(random_datetime(730)),
        })
    return rows

def gen_orders(n, customers):
    rows = []
    for i in range(1, n + 1):
        c = random.choice(customers)
        created = random_datetime(365)
        updated = created + timedelta(hours=random.randint(1, 240))
        rows.append({
            "order_id": i,
            "customer_id": c["customer_id"],
            "status": random.choice(ORDER_STATUSES),
            "payment_method": random.choice(PAYMENT_METHODS),
            "total_amount": round(random.uniform(500, 250_000), 2),
            "currency": "RUB",
            "created_at": iso(created),
            "updated_at": iso(updated),
            "shipping_city": c["city"],
            "shipping_country": c["country"],
        })
    return rows

def gen_order_items(n, orders, products):
    rows = []
    for i in range(1, n + 1):
        o = random.choice(orders)
        p = random.choice(products)
        q = random.randint(1, 5)
        d = round(random.uniform(0, 0.3), 2)
        rows.append({
            "order_item_id": i,
            "order_id": o["order_id"],
            "product_id": p["product_id"],
            "quantity": q,
            "unit_price": p["price"],
            "discount": d,
            "line_total": round(q * p["price"] * (1 - d), 2),
        })
    return rows

def gen_events(n, customers, products):
    rows = []
    for _ in range(1, n + 1):
        rows.append({
            "event_id": str(uuid.uuid4()),
            "customer_id": random.choice(customers)["customer_id"],
            "product_id": random.choice(products)["product_id"],
            "event_type": random.choice(EVENT_TYPES),
            "device": random.choice(DEVICES),
            "channel": random.choice(CHANNELS),
            "event_time": iso(random_datetime(180)),
            "session_id": str(uuid.uuid4()),
        })
    return rows


# --- S3 ---
def make_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY,
        region_name=S3_REGION,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )

def ensure_bucket(s3, bucket):
    try:
        s3.head_bucket(Bucket=bucket)
        print(f"  ✓ Bucket '{bucket}' уже есть")
    except ClientError:
        s3.create_bucket(Bucket=bucket)
        print(f"  + Создан bucket '{bucket}'")

def s3_key(table_name: str, part_num: int) -> str:
    return f"{LAYER}/{table_name}/{PARTITION_DATE}/{table_name}_part_{part_num:03d}.csv"

def upload_table(s3, table_name, rows):
    total, total_bytes = 0, 0
    for part_num, chunk in chunked(rows, CHUNK_SIZE):
        payload = rows_to_csv_bytes(chunk)
        key = s3_key(table_name, part_num)
        s3.put_object(Bucket=S3_BUCKET, Key=key, Body=payload, ContentType="text/csv")
        total += len(chunk)
        total_bytes += len(payload)
        print(f"    → s3://{S3_BUCKET}/{key}  ({len(chunk)} строк)")

        if WRITE_LOCAL:
            p = LOCAL_DIR / LAYER / table_name / PARTITION_DATE / f"{table_name}_part_{part_num:03d}.csv"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(payload)

    print(f"  ✓ {table_name}: {total} строк ({total_bytes/1024:.1f} KB)")


def main():
    print(f"Генерация данных: rows={ROWS}, chunk={CHUNK_SIZE}, seed={RANDOM_SEED}")
    print(f"S3: {S3_ENDPOINT}, bucket={S3_BUCKET}, layer={LAYER}, partition={PARTITION_DATE}\n")

    customers   = gen_customers(ROWS)
    products    = gen_products(ROWS)
    orders      = gen_orders(ROWS, customers)
    order_items = gen_order_items(ROWS, orders, products)
    events      = gen_events(ROWS, customers, products)
    print("Сущности сгенерированы.\n")

    s3 = make_s3_client()
    ensure_bucket(s3, S3_BUCKET)
    print()

    for name, rows in [
        ("customers", customers),
        ("products", products),
        ("orders", orders),
        ("order_items", order_items),
        ("events", events),
    ]:
        upload_table(s3, name, rows)

    print("\nЗагрузка в S3 завершена.")


if __name__ == "__main__":
    main()