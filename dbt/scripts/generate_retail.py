"""
Генератор retail / e-commerce данных.

Создаёт 11 связанных таблиц, загружает их в MinIO по пути
retail/stg/{table}/{date}/*.csv и сохраняет схему для загрузчика.

Пайплайн supply_chain не затрагивается: используется отдельный префикс retail/stg.
"""

import csv
import io
import json
import os
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

try:
    import boto3
    from botocore.client import Config
    from botocore.exceptions import ClientError
except ImportError:
    print("Требуется boto3. Установите: pip install boto3", file=sys.stderr)
    sys.exit(1)


SEED          = int(os.getenv("RETAIL_SEED", "42"))
CUSTOMERS     = int(os.getenv("RETAIL_CUSTOMERS", "3000"))
ORDERS        = int(os.getenv("RETAIL_ORDERS", "5000"))
PRODUCTS      = int(os.getenv("RETAIL_PRODUCTS", "500"))
STORES        = int(os.getenv("RETAIL_STORES", "50"))
PROMOTIONS    = int(os.getenv("RETAIL_PROMOTIONS", "30"))
REVIEWS       = int(os.getenv("RETAIL_REVIEWS", "2000"))
CHUNK_SIZE    = int(os.getenv("CHUNK_SIZE", "2500"))

S3_ENDPOINT   = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
S3_ACCESS_KEY = os.getenv("MINIO_ROOT_USER", "minioadmin")
S3_SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
S3_BUCKET     = os.getenv("MINIO_BUCKET", "dbt-bucket")
S3_REGION     = os.getenv("MINIO_REGION", "us-east-1")
PREFIX        = os.getenv("RETAIL_PREFIX", "retail/stg").strip("/")

CLEAN_BEFORE_UPLOAD = os.getenv("CLEAN_BEFORE_UPLOAD", "true").lower() in ("1", "true", "yes")
PARTITION_DATE      = os.getenv("PARTITION_DATE", datetime.utcnow().strftime("%Y-%m-%d"))
SCHEMA_JSON_PATH    = Path(os.getenv("RETAIL_SCHEMA_JSON_PATH", "/tmp/_retail_schema.json"))
BASE_DATE           = datetime.utcnow().date()


SCHEMAS = {
    "categories": [
        ("category_id", "INT"),
        ("category_name", "VARCHAR(100)"),
        ("department", "VARCHAR(50)"),
        ("is_active", "TINYINT"),
    ],
    "products": [
        ("product_id", "INT"),
        ("product_name", "VARCHAR(200)"),
        ("category_id", "INT"),
        ("brand", "VARCHAR(100)"),
        ("unit_price", "DECIMAL(12,2)"),
        ("cost", "DECIMAL(12,2)"),
        ("launch_date", "DATE"),
        ("is_active", "TINYINT"),
    ],
    "customers": [
        ("customer_id", "INT"),
        ("first_name", "VARCHAR(100)"),
        ("last_name", "VARCHAR(100)"),
        ("email", "VARCHAR(255)"),
        ("city", "VARCHAR(100)"),
        ("country", "VARCHAR(10)"),
        ("signup_date", "DATE"),
        ("segment", "VARCHAR(50)"),
        ("loyalty_tier", "VARCHAR(50)"),
        ("is_active", "TINYINT"),
    ],
    "stores": [
        ("store_id", "INT"),
        ("store_name", "VARCHAR(150)"),
        ("city", "VARCHAR(100)"),
        ("country", "VARCHAR(10)"),
        ("store_type", "VARCHAR(50)"),
        ("opened_date", "DATE"),
        ("is_active", "TINYINT"),
    ],
    "promotions": [
        ("promotion_id", "INT"),
        ("promotion_name", "VARCHAR(150)"),
        ("promo_type", "VARCHAR(50)"),
        ("discount_pct", "DECIMAL(5,2)"),
        ("start_date", "DATE"),
        ("end_date", "DATE"),
        ("channel", "VARCHAR(50)"),
        ("is_active", "TINYINT"),
    ],
    "orders": [
        ("order_id", "INT"),
        ("customer_id", "INT"),
        ("store_id", "INT"),
        ("promotion_id", "INT"),
        ("order_date", "DATETIME"),
        ("status", "VARCHAR(50)"),
        ("channel", "VARCHAR(50)"),
        ("currency", "VARCHAR(10)"),
        ("subtotal", "DECIMAL(14,2)"),
        ("discount_amount", "DECIMAL(14,2)"),
        ("shipping_cost", "DECIMAL(14,2)"),
        ("tax_amount", "DECIMAL(14,2)"),
        ("total_amount", "DECIMAL(14,2)"),
    ],
    "order_items": [
        ("order_item_id", "INT"),
        ("order_id", "INT"),
        ("product_id", "INT"),
        ("quantity", "INT"),
        ("unit_price", "DECIMAL(12,2)"),
        ("discount_pct", "DECIMAL(5,2)"),
        ("line_total", "DECIMAL(14,2)"),
    ],
    "payments": [
        ("payment_id", "INT"),
        ("order_id", "INT"),
        ("payment_date", "DATETIME"),
        ("payment_method", "VARCHAR(50)"),
        ("amount", "DECIMAL(14,2)"),
        ("status", "VARCHAR(50)"),
        ("transaction_ref", "VARCHAR(100)"),
    ],
    "shipments": [
        ("shipment_id", "INT"),
        ("order_id", "INT"),
        ("carrier", "VARCHAR(100)"),
        ("shipping_method", "VARCHAR(50)"),
        ("shipped_date", "DATE"),
        ("promised_date", "DATE"),
        ("delivered_date", "DATE"),
        ("status", "VARCHAR(50)"),
        ("tracking_number", "VARCHAR(100)"),
    ],
    "returns": [
        ("return_id", "INT"),
        ("order_id", "INT"),
        ("return_date", "DATE"),
        ("reason", "VARCHAR(150)"),
        ("status", "VARCHAR(50)"),
        ("refund_amount", "DECIMAL(14,2)"),
    ],
    "reviews": [
        ("review_id", "INT"),
        ("product_id", "INT"),
        ("customer_id", "INT"),
        ("order_id", "INT"),
        ("rating", "INT"),
        ("review_date", "DATE"),
        ("review_text", "VARCHAR(500)"),
        ("helpful_votes", "INT"),
    ],
}


FIRST_NAMES = ["Ivan", "Petr", "Sergey", "Alexey", "Dmitry", "Andrey", "Mikhail",
               "Nikolay", "Vladimir", "Egor", "Maria", "Anna", "Elena", "Olga",
               "Tatiana", "Natalia", "Irina", "Svetlana", "Yulia", "Ekaterina"]
LAST_NAMES = ["Ivanov", "Petrov", "Sidorov", "Smirnov", "Kuznetsov", "Popov",
              "Vasiliev", "Sokolov", "Mikhailov", "Novikov", "Fedorov", "Morozov",
              "Volkov", "Alekseev", "Lebedev", "Semenov", "Egorov", "Pavlov"]
CITIES = ["Moscow", "Saint Petersburg", "Novosibirsk", "Ekaterinburg", "Kazan",
          "Nizhny Novgorod", "Chelyabinsk", "Samara", "Omsk", "Rostov-on-Don",
          "Ufa", "Krasnoyarsk", "Voronezh", "Perm", "Volgograd"]
COUNTRIES = ["RU", "KZ", "BY", "CN", "TR", "AE", "IN", "DE", "PL", "US"]
SEGMENTS = ["new", "regular", "vip", "wholesale"]
LOYALTY_TIERS = ["Bronze", "Silver", "Gold", "Platinum"]
STORE_TYPES = ["flagship", "mall", "outlet", "online", "popup"]
PROMO_TYPES = ["percent", "fixed", "free_shipping", "bogo"]
CHANNELS = ["web", "mobile", "store", "marketplace"]
ORDER_STATUSES = ["completed", "delivered", "shipped", "processing", "cancelled", "returned"]
PAYMENT_METHODS = ["card", "cash", "bank_transfer", "wallet", "bnpl"]
CARRIERS = ["DHL", "UPS", "FedEx", "CDEK", "Boxberry", "Post"]
SHIPPING_METHODS = ["standard", "express", "same_day", "pickup"]
RETURN_REASONS = ["damaged", "wrong_item", "not_as_described", "changed_mind", "late_delivery"]
REVIEW_WORDS = ["Excellent", "Good", "Average", "Poor", "Great"]
CATEGORY_NAMES = [
    ("Electronics", "Technology"), ("Computers", "Technology"), ("Phones", "Technology"),
    ("Home", "Home & Living"), ("Kitchen", "Home & Living"), ("Furniture", "Home & Living"),
    ("Fashion", "Apparel"), ("Shoes", "Apparel"), ("Accessories", "Apparel"),
    ("Beauty", "Health & Beauty"), ("Health", "Health & Beauty"), ("Sports", "Sports"),
    ("Outdoor", "Sports"), ("Toys", "Kids"), ("Baby", "Kids"),
    ("Books", "Media"), ("Music", "Media"), ("Gaming", "Media"),
    ("Auto", "Auto"), ("Garden", "Home & Living"),
]
PRODUCT_ADJ = ["Smart", "Premium", "Classic", "Compact", "Pro", "Eco", "Ultra", "Basic"]
PRODUCT_NOUN = ["Speaker", "Laptop", "Phone", "Chair", "Blender", "Jacket", "Sneakers",
                "Watch", "Cream", "Bike", "Tent", "Toy", "Book", "Console", "Lamp"]


def rand_date(days_back, rng):
    return (BASE_DATE - timedelta(days=rng.randint(0, days_back))).isoformat()


def rand_datetime(days_back, rng):
    dt = datetime.utcnow() - timedelta(
        days=rng.randint(0, days_back),
        hours=rng.randint(0, 23),
        minutes=rng.randint(0, 59),
        seconds=rng.randint(0, 59),
    )
    return dt


def make_s3_client():
    return boto3.client(
        "s3", endpoint_url=S3_ENDPOINT,
        aws_access_key_id=S3_ACCESS_KEY, aws_secret_access_key=S3_SECRET_KEY,
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


def clean_prefix(s3, prefix):
    deleted = 0
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=prefix):
        contents = page.get("Contents", [])
        if not contents:
            continue
        for i in range(0, len(contents), 1000):
            batch = contents[i:i + 1000]
            s3.delete_objects(
                Bucket=S3_BUCKET,
                Delete={"Objects": [{"Key": o["Key"]} for o in batch]},
            )
            deleted += len(batch)
    return deleted


def rows_to_csv_bytes(rows, columns):
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns)
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")


def upload_table(s3, table_name, rows):
    columns = [c for c, _ in SCHEMAS[table_name]]
    if CLEAN_BEFORE_UPLOAD:
        n = clean_prefix(s3, f"{PREFIX}/{table_name}/")
        if n:
            print(f"    очищено {n} старых объектов под {PREFIX}/{table_name}/")

    total = 0
    for part_num, start in enumerate(range(0, len(rows), CHUNK_SIZE), start=1):
        chunk = rows[start:start + CHUNK_SIZE]
        payload = rows_to_csv_bytes(chunk, columns)
        key = f"{PREFIX}/{table_name}/{PARTITION_DATE}/{table_name}_part_{part_num:03d}.csv"
        s3.put_object(Bucket=S3_BUCKET, Key=key, Body=payload, ContentType="text/csv")
        total += len(payload)
        print(f"    → s3://{S3_BUCKET}/{key} ({len(chunk)} строк)")

    print(f"  ✓ {table_name}: {len(rows)} строк, {len(columns)} колонок, "
          f"{total / 1024 / 1024:.2f} MB")


def build_data():
    rng = random.Random(SEED)

    categories = []
    for i, (name, dept) in enumerate(CATEGORY_NAMES, start=1):
        categories.append({
            "category_id": i,
            "category_name": name,
            "department": dept,
            "is_active": 1,
        })

    products = []
    for i in range(1, PRODUCTS + 1):
        category = rng.choice(categories)
        unit_price = round(rng.uniform(5, 1500), 2)
        products.append({
            "product_id": i,
            "product_name": f"{rng.choice(PRODUCT_ADJ)} {rng.choice(PRODUCT_NOUN)} {rng.randint(100, 999)}",
            "category_id": category["category_id"],
            "brand": rng.choice(["BrandA", "BrandB", "BrandC", "VendorX", "NoName"]),
            "unit_price": unit_price,
            "cost": round(unit_price * rng.uniform(0.45, 0.8), 2),
            "launch_date": rand_date(3 * 365, rng),
            "is_active": 1 if rng.random() < 0.92 else 0,
        })

    customers = []
    for i in range(1, CUSTOMERS + 1):
        customers.append({
            "customer_id": i,
            "first_name": rng.choice(FIRST_NAMES),
            "last_name": rng.choice(LAST_NAMES),
            "email": f"customer{i}@example.com",
            "city": rng.choice(CITIES),
            "country": rng.choice(COUNTRIES),
            "signup_date": rand_date(3 * 365, rng),
            "segment": rng.choice(SEGMENTS),
            "loyalty_tier": rng.choice(LOYALTY_TIERS),
            "is_active": 1 if rng.random() < 0.95 else 0,
        })

    stores = []
    for i in range(1, STORES + 1):
        stores.append({
            "store_id": i,
            "store_name": f"Store {i:03d}",
            "city": rng.choice(CITIES),
            "country": rng.choice(COUNTRIES),
            "store_type": rng.choice(STORE_TYPES),
            "opened_date": rand_date(5 * 365, rng),
            "is_active": 1 if rng.random() < 0.9 else 0,
        })

    promotions = [{
        "promotion_id": 0,
        "promotion_name": "No Promotion",
        "promo_type": "none",
        "discount_pct": 0,
        "start_date": (BASE_DATE - timedelta(days=365)).isoformat(),
        "end_date": (BASE_DATE + timedelta(days=365)).isoformat(),
        "channel": "all",
        "is_active": 1,
    }]
    for i in range(1, PROMOTIONS + 1):
        start = BASE_DATE - timedelta(days=rng.randint(0, 300))
        promotions.append({
            "promotion_id": i,
            "promotion_name": f"Promo {i:02d}",
            "promo_type": rng.choice(PROMO_TYPES),
            "discount_pct": round(rng.uniform(5, 40), 2),
            "start_date": start.isoformat(),
            "end_date": (start + timedelta(days=rng.randint(7, 60))).isoformat(),
            "channel": rng.choice(CHANNELS + ["all"]),
            "is_active": 1 if rng.random() < 0.85 else 0,
        })

    orders = []
    order_items = []
    order_meta = []
    item_id = 0

    for order_id in range(1, ORDERS + 1):
        customer = rng.choice(customers)
        store = rng.choice(stores)
        promo = rng.choice(promotions) if rng.random() < 0.35 else promotions[0]
        order_dt = rand_datetime(365, rng)
        status = rng.choices(ORDER_STATUSES, weights=[45, 25, 12, 10, 5, 3])[0]
        channel = rng.choice(CHANNELS)

        n_items = rng.choices([1, 2, 3, 4], weights=[40, 35, 20, 5])[0]
        subtotal_gross = 0.0
        discount_total = 0.0
        net_items = 0.0

        for _ in range(n_items):
            product = rng.choice(products)
            quantity = rng.choices([1, 2, 3, 4, 5], weights=[55, 25, 12, 5, 3])[0]
            unit_price = product["unit_price"]
            discount_pct = promo["discount_pct"] if promo["promotion_id"] else 0
            gross = unit_price * quantity
            line_total = round(gross * (1 - discount_pct / 100), 2)
            item_id += 1
            order_items.append({
                "order_item_id": item_id,
                "order_id": order_id,
                "product_id": product["product_id"],
                "quantity": quantity,
                "unit_price": unit_price,
                "discount_pct": discount_pct,
                "line_total": line_total,
            })
            subtotal_gross += gross
            discount_total += gross - line_total
            net_items += line_total

        shipping_cost = 0.0 if channel == "store" else round(rng.uniform(0, 25), 2)
        tax_amount = round(net_items * 0.08, 2)
        total_amount = round(net_items + shipping_cost + tax_amount, 2)

        orders.append({
            "order_id": order_id,
            "customer_id": customer["customer_id"],
            "store_id": store["store_id"],
            "promotion_id": promo["promotion_id"],
            "order_date": order_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "status": status,
            "channel": channel,
            "currency": "USD",
            "subtotal": round(subtotal_gross, 2),
            "discount_amount": round(discount_total, 2),
            "shipping_cost": shipping_cost,
            "tax_amount": tax_amount,
            "total_amount": total_amount,
        })
        order_meta.append((order_dt, status))

    payments = []
    for order, (order_dt, status) in zip(orders, order_meta):
        if status in ("completed", "delivered", "shipped"):
            pay_status = "paid"
        elif status == "returned":
            pay_status = "refunded"
        elif status == "cancelled":
            pay_status = "failed"
        else:
            pay_status = "pending"
        pay_dt = order_dt + timedelta(minutes=rng.randint(1, 1440))
        payments.append({
            "payment_id": order["order_id"],
            "order_id": order["order_id"],
            "payment_date": pay_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "payment_method": rng.choice(PAYMENT_METHODS),
            "amount": order["total_amount"],
            "status": pay_status,
            "transaction_ref": f"TXN-{order['order_id']:08d}",
        })

    shipments = []
    shipment_id = 0
    for order, (order_dt, status) in zip(orders, order_meta):
        if status not in ("completed", "delivered", "shipped"):
            continue
        shipment_id += 1
        shipped = order_dt + timedelta(days=rng.randint(0, 2))
        promised = shipped + timedelta(days=rng.randint(1, 7))
        delivered = promised + timedelta(days=rng.choice([-1, 0, 0, 1, 2, 3]))
        shipments.append({
            "shipment_id": shipment_id,
            "order_id": order["order_id"],
            "carrier": rng.choice(CARRIERS),
            "shipping_method": rng.choice(SHIPPING_METHODS),
            "shipped_date": shipped.date().isoformat(),
            "promised_date": promised.date().isoformat(),
            "delivered_date": delivered.date().isoformat(),
            "status": "delivered" if delivered.date() <= promised.date() else "delayed",
            "tracking_number": f"TRK{shipment_id:010d}",
        })

    delivered_orders = [
        (order, meta) for order, meta in zip(orders, order_meta)
        if meta[1] in ("completed", "delivered", "returned")
    ]
    return_count = min(len(delivered_orders), max(100, int(len(delivered_orders) * 0.08)))
    sampled = rng.sample(delivered_orders, return_count)
    returns = []
    for i, (order, (order_dt, _)) in enumerate(sampled, start=1):
        returns.append({
            "return_id": i,
            "order_id": order["order_id"],
            "return_date": (order_dt + timedelta(days=rng.randint(1, 30))).date().isoformat(),
            "reason": rng.choice(RETURN_REASONS),
            "status": rng.choice(["approved", "pending", "rejected", "refunded"]),
            "refund_amount": round(order["total_amount"] * rng.uniform(0.3, 1.0), 2),
        })

    reviews = []
    for i in range(1, REVIEWS + 1):
        product = rng.choice(products)
        customer = rng.choice(customers)
        order, (order_dt, _) = rng.choice(list(zip(orders, order_meta)))
        reviews.append({
            "review_id": i,
            "product_id": product["product_id"],
            "customer_id": customer["customer_id"],
            "order_id": order["order_id"],
            "rating": rng.choices([1, 2, 3, 4, 5], weights=[5, 8, 15, 35, 37])[0],
            "review_date": (order_dt + timedelta(days=rng.randint(1, 60))).date().isoformat(),
            "review_text": f"{rng.choice(REVIEW_WORDS)} product review {i}",
            "helpful_votes": rng.randint(0, 50),
        })

    return {
        "categories": categories,
        "products": products,
        "customers": customers,
        "stores": stores,
        "promotions": promotions,
        "orders": orders,
        "order_items": order_items,
        "payments": payments,
        "shipments": shipments,
        "returns": returns,
        "reviews": reviews,
    }


def main():
    print("=" * 60)
    print("  Retail / e-commerce data generation")
    print("=" * 60)
    print(f"  seed={SEED}, customers={CUSTOMERS}, orders={ORDERS}, products={PRODUCTS}")
    print(f"  S3: {S3_ENDPOINT}, bucket={S3_BUCKET}, prefix={PREFIX}, partition={PARTITION_DATE}\n")

    data = build_data()
    s3 = make_s3_client()
    ensure_bucket(s3, S3_BUCKET)
    print()

    for table_name in SCHEMAS:
        print(f">>> {table_name}")
        upload_table(s3, table_name, data[table_name])
        print()

    schema = {name: {"columns": SCHEMAS[name]} for name in SCHEMAS}
    SCHEMA_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCHEMA_JSON_PATH.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ✓ Схема сохранена: {SCHEMA_JSON_PATH}")
    print(f"\n✅ Retail: {len(SCHEMAS)} таблиц загружено в S3.")


if __name__ == "__main__":
    main()
