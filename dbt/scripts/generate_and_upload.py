"""
Генератор бизнес-данных о поставках.

Создаёт 15 stg-таблиц по 120+ колонок каждая. Для каждой таблицы есть
фиксированный набор «ядровых» колонок, нужных mart-слою, остальные
добираются из пула случайно.

Перед загрузкой удаляет все старые объекты под префиксом
stg/{table}/ — это гарантирует отсутствие дубликатов в S3.

Также генерирует dbt-модели (stg_*.sql) и sources.yml.
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


# ---------- Настройки ----------
ROWS              = int(os.getenv("ROWS", "5000"))
CHUNK_SIZE        = int(os.getenv("CHUNK_SIZE", "2500"))
RANDOM_SEED       = int(os.getenv("RANDOM_SEED", "42"))
COLUMNS_PER_TABLE = int(os.getenv("COLUMNS_PER_TABLE", "120"))

S3_ENDPOINT   = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
S3_ACCESS_KEY = os.getenv("MINIO_ROOT_USER", "minioadmin")
S3_SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
S3_BUCKET     = os.getenv("MINIO_BUCKET", "dbt-bucket")
S3_REGION     = os.getenv("MINIO_REGION", "us-east-1")
LAYER         = os.getenv("LAYER", "stg")

# Очищать ли префикс stg/{table}/ перед загрузкой (дедупликация)
CLEAN_BEFORE_UPLOAD = os.getenv("CLEAN_BEFORE_UPLOAD", "true").lower() in ("1", "true", "yes")

PARTITION_DATE = os.getenv("PARTITION_DATE", datetime.utcnow().strftime("%Y-%m-%d"))

DBT_PROJECT_DIR  = Path(os.getenv("DBT_PROJECT_DIR", "/dbt/project"))
SCHEMA_JSON_PATH = Path(os.getenv("SCHEMA_JSON_PATH", "/dbt/_schema.json"))


# ---------- Справочники ----------
FIRST_NAMES = ["Иван","Пётр","Сергей","Алексей","Дмитрий","Андрей","Михаил",
               "Николай","Владимир","Егор","Мария","Анна","Елена","Ольга",
               "Татьяна","Наталья","Ирина","Светлана","Юлия","Екатерина"]
LAST_NAMES = ["Иванов","Петров","Сидоров","Смирнов","Кузнецов","Попов",
              "Васильев","Соколов","Михайлов","Новиков","Фёдоров","Морозов",
              "Волков","Алексеев","Лебедев","Семёнов","Егоров","Павлов"]
CITIES = ["Москва","Санкт-Петербург","Новосибирск","Екатеринбург","Казань",
          "Нижний Новгород","Челябинск","Самара","Омск","Ростов-на-Дону",
          "Уфа","Красноярск","Воронеж","Пермь","Волгоград"]
COUNTRIES = ["RU","CN","DE","TR","US","IT","IN","KR","JP","PL","FR","ES","NL","CZ","KZ"]
REGIONS = ["Moscow","North-West","Volga","Ural","Siberia","South","Far East"]
CATEGORIES = ["Electronics","Machinery","Raw Materials","Food","Chemicals",
              "Textiles","Auto Parts","Pharma","Packaging","Equipment"]
SUBCATEGORIES = ["Class A","Class B","Class C","Premium","Standard",
                 "Economy","Industrial","Consumer","Custom"]
BRANDS = ["BrandA","BrandB","BrandC","BrandD","VendorX","VendorY","NoName"]
PRODUCTS = ["Болт М8","Кабель UTP","Резистор 10k","Микросхема","Подшипник",
            "Мотор 5kW","Насос","Клапан","Датчик","Плата","Реле","Контактор"]
INCOTERMS = ["EXW","FCA","FAS","FOB","CFR","CIF","CPT","CIP","DAP","DPU","DDP"]
PAYMENT_TERMS = ["Net 30","Net 60","Net 90","Prepaid","COD","LC","DA","DP"]
CURRENCIES = ["RUB","USD","EUR","CNY","TRY","KZT","BYN"]
UNITS = ["pcs","kg","m","m2","m3","L","box","pallet","set","roll","drum"]
STATUSES = ["draft","pending","approved","in_progress","shipped",
            "delivered","completed","cancelled","returned","on_hold"]
PAYMENT_STATUSES = ["unpaid","partial","paid","overdue","refunded","disputed"]
SHIP_TYPES = ["full","partial","split","consolidated","direct","drop_ship"]
TRANSPORT_MODES = ["road","rail","sea","air","multimodal","courier","pipeline"]
CONTAINER_TYPES = ["20ft","40ft","40HC","45HC","LTL","FTL","reefer","tank","open_top"]
PRIORITIES = ["low","normal","high","critical","urgent"]
QUALITY_GRADES = ["A+","A","B","C","D","F"]
HAZARD_CLASSES = ["none","1","2","3","4","5","6","7","8","9"]
PACKAGING_TYPES = ["box","carton","pallet","crate","bag","drum","tank","bundle"]
LOADING_TYPES = ["manual","forklift","crane","conveyor","ro-ro","pump"]
CUSTOMS_REGIMES = ["export","import","transit","temporary","re-export","bonded"]
DELIVERY_TERMS = ["DAP","DDP","FOB","CIF","EXW","FCA"]
DIRECTIONS = ["in","out","transfer","adjustment","writeoff"]

ENUM_VALUES = {
    "incoterms": INCOTERMS, "payment_terms": PAYMENT_TERMS,
    "currency": CURRENCIES, "uom": UNITS, "status": STATUSES,
    "payment_status": PAYMENT_STATUSES, "shipment_type": SHIP_TYPES,
    "transport_mode": TRANSPORT_MODES, "container_type": CONTAINER_TYPES,
    "priority": PRIORITIES, "quality_grade": QUALITY_GRADES,
    "hazard_class": HAZARD_CLASSES, "packaging_type": PACKAGING_TYPES,
    "loading_type": LOADING_TYPES, "customs_regime": CUSTOMS_REGIMES,
    "delivery_terms": DELIVERY_TERMS, "direction": DIRECTIONS,
}

KIND_TO_PG = {
    "code": "TEXT", "date": "DATE", "datetime": "TIMESTAMP",
    "money": "NUMERIC(15,2)", "int": "INTEGER", "float": "NUMERIC(15,3)",
    "name": "TEXT", "product": "TEXT", "category": "TEXT",
    "subcategory": "TEXT", "brand": "TEXT", "model": "TEXT",
    "country": "TEXT", "city": "TEXT", "region": "TEXT",
    "bool": "BOOLEAN", "coord": "NUMERIC(10,6)",
    "text": "TEXT", "email": "TEXT", "phone": "TEXT", "url": "TEXT",
}
for _e in ENUM_VALUES:
    KIND_TO_PG[_e] = "TEXT"


# ---------- Пул «мусорных» колонок ----------
COLUMN_POOL = [
    ("contract_number", "code"), ("invoice_number", "code"),
    ("waybill_number", "code"), ("ttn_number", "code"),
    ("packing_list_number", "code"), ("customs_declaration_number", "code"),
    ("batch_number", "code"), ("serial_number", "code"), ("sku", "code"),
    ("gtin", "code"), ("upc", "code"), ("ean", "code"), ("hs_code", "code"),
    ("eccn_code", "code"), ("seal_number", "code"), ("container_id", "code"),
    ("trailer_id", "code"), ("route_code", "code"), ("warehouse_code", "code"),
    ("dock_number", "code"), ("tracking_number", "code"),
    ("supplier_code", "code"), ("buyer_code", "code"), ("product_code", "code"),
    ("purchase_order_number", "code"), ("sales_order_number", "code"),
    ("delivery_note_number", "code"), ("proforma_number", "code"),
    ("bill_of_lading", "code"), ("air_waybill", "code"),

    ("order_date", "date"), ("ship_date", "date"), ("delivery_date", "date"),
    ("due_date", "date"), ("received_date", "date"), ("invoice_date", "date"),
    ("payment_date", "date"), ("contract_date", "date"), ("expiry_date", "date"),
    ("production_date", "date"), ("customs_clearance_date", "date"),
    ("arrival_date", "date"), ("departure_date", "date"),
    ("loading_date", "date"), ("unloading_date", "date"), ("eta_date", "date"),
    ("etd_date", "date"), ("inspection_date", "date"),
    ("certification_date", "date"), ("warranty_start_date", "date"),
    ("warranty_end_date", "date"), ("registration_date", "date"),
    ("approval_date", "date"), ("cancellation_date", "date"),
    ("return_date", "date"), ("movement_date", "date"),

    ("created_at", "datetime"), ("updated_at", "datetime"),
    ("shipped_at", "datetime"), ("delivered_at", "datetime"),
    ("scanned_at", "datetime"), ("checked_at", "datetime"),
    ("packed_at", "datetime"), ("loaded_at", "datetime"),
    ("unloaded_at", "datetime"), ("paid_at", "datetime"),

    ("unit_price", "money"), ("total_price", "money"), ("total_amount", "money"),
    ("net_amount", "money"), ("gross_amount", "money"), ("tax_amount", "money"),
    ("vat_amount", "money"), ("discount_amount", "money"),
    ("shipping_cost", "money"), ("insurance_cost", "money"),
    ("customs_duty", "money"), ("excise_amount", "money"), ("subtotal", "money"),
    ("margin", "money"), ("markup", "money"), ("rebate", "money"),
    ("freight_cost", "money"), ("storage_cost", "money"),
    ("handling_cost", "money"), ("packaging_cost", "money"),
    ("loading_cost", "money"), ("unloading_cost", "money"),
    ("customs_fee", "money"), ("brokerage_fee", "money"),
    ("port_charges", "money"), ("demurrage_cost", "money"),

    ("quantity", "int"), ("boxes", "int"), ("pallets", "int"), ("cartons", "int"),
    ("units_per_box", "int"), ("items_per_pallet", "int"), ("containers", "int"),
    ("trips", "int"), ("min_stock", "int"), ("max_stock", "int"),
    ("reorder_point", "int"), ("safety_stock", "int"),
    ("available_stock", "int"), ("reserved_stock", "int"), ("damaged_units", "int"),

    ("weight_kg", "float"), ("gross_weight_kg", "float"), ("net_weight_kg", "float"),
    ("tare_weight_kg", "float"), ("volume_m3", "float"), ("cubic_meters", "float"),
    ("length_cm", "float"), ("width_cm", "float"), ("height_cm", "float"),
    ("density_kg_m3", "float"), ("payload_kg", "float"), ("capacity_m3", "float"),
    ("max_load_kg", "float"), ("empty_weight_kg", "float"),
    ("cargo_weight_kg", "float"),

    ("supplier_name", "name"), ("buyer_name", "name"), ("carrier_name", "name"),
    ("warehouse_name", "name"), ("driver_name", "name"), ("manager_name", "name"),
    ("contact_person", "name"), ("signatory", "name"), ("inspector_name", "name"),
    ("responsible_person", "name"), ("product_name", "product"),
    ("company_name", "name"), ("legal_entity_name", "name"),
    ("brand_name", "name"), ("manufacturer_name", "name"),

    ("category", "category"), ("subcategory", "subcategory"),
    ("brand", "brand"), ("model", "model"),
    ("country_origin", "country"), ("country_destination", "country"),
    ("city_from", "city"), ("city_to", "city"), ("region", "region"),
    ("city", "city"), ("country", "country"),
    ("incoterms", "incoterms"), ("payment_terms", "payment_terms"),
    ("currency", "currency"), ("unit_of_measure", "uom"),
    ("status", "status"), ("payment_status", "payment_status"),
    ("shipment_type", "shipment_type"), ("transport_mode", "transport_mode"),
    ("container_type", "container_type"), ("priority", "priority"),
    ("quality_grade", "quality_grade"), ("hazard_class", "hazard_class"),
    ("packaging_type", "packaging_type"), ("loading_type", "loading_type"),
    ("customs_regime", "customs_regime"), ("delivery_terms", "delivery_terms"),
    ("direction", "direction"),

    ("is_urgent", "bool"), ("is_hazardous", "bool"), ("is_fragile", "bool"),
    ("is_refrigerated", "bool"), ("is_oversized", "bool"),
    ("has_insurance", "bool"), ("has_customs", "bool"), ("is_prepaid", "bool"),
    ("is_returned", "bool"), ("is_damaged", "bool"), ("quality_passed", "bool"),
    ("safety_certified", "bool"), ("temperature_controlled", "bool"),
    ("is_export", "bool"), ("is_import", "bool"),

    ("temperature_c", "float"), ("humidity_pct", "float"), ("pressure_kpa", "float"),
    ("distance_km", "int"), ("eta_hours", "int"), ("rating", "float"),
    ("latitude", "coord"), ("longitude", "coord"),
    ("notes", "text"), ("comments", "text"), ("description", "text"),
    ("contact_email", "email"), ("contact_phone", "phone"),
    ("website", "url"), ("tracking_url", "url"),
]


# ---------- Таблицы ----------
TABLES = [
    ("suppliers", [
        ("supplier_name", "name"), ("country", "country"), ("city", "city"),
        ("region", "region"), ("rating", "float"), ("registration_date", "date"),
    ], []),

    ("supply_contracts", [
        ("contract_number", "code"), ("contract_date", "date"),
        ("expiry_date", "date"), ("total_price", "money"),
        ("currency", "currency"), ("status", "status"),
        ("payment_terms", "payment_terms"),
    ], [("supplier_id", "suppliers")]),

    ("supply_orders", [
        ("order_date", "date"), ("status", "status"),
        ("total_price", "money"), ("currency", "currency"),
        ("priority", "priority"), ("delivery_date", "date"),
    ], [("supplier_id", "suppliers"),
        ("supply_contract_id", "supply_contracts")]),

    ("supply_items", [
        ("product_name", "product"), ("category", "category"),
        ("quantity", "int"), ("unit_price", "money"),
        ("total_price", "money"), ("unit_of_measure", "uom"),
    ], [("supply_order_id", "supply_orders")]),

    ("shipments", [
        ("ship_date", "date"), ("delivery_date", "date"),
        ("transport_mode", "transport_mode"), ("container_type", "container_type"),
        ("weight_kg", "float"), ("shipping_cost", "money"), ("status", "status"),
    ], [("supply_order_id", "supply_orders")]),

    ("warehouses", [
        ("warehouse_name", "name"), ("city", "city"),
        ("country", "country"), ("capacity_m3", "float"),
    ], []),

    ("deliveries", [
        ("delivery_date", "date"), ("received_date", "date"),
        ("status", "status"),
    ], [("shipment_id", "shipments"), ("warehouse_id", "warehouses")]),

    ("invoices", [
        ("invoice_number", "code"), ("invoice_date", "date"),
        ("total_price", "money"), ("currency", "currency"),
        ("payment_status", "payment_status"),
    ], [("supply_order_id", "supply_orders")]),

    ("payments", [
        ("payment_date", "date"), ("total_price", "money"),
        ("currency", "currency"), ("payment_status", "payment_status"),
    ], [("invoice_id", "invoices")]),

    ("quality_checks", [
        ("quality_grade", "quality_grade"), ("quality_passed", "bool"),
        ("inspector_name", "name"), ("checked_at", "datetime"),
    ], [("supply_item_id", "supply_items")]),

    ("returns", [
        ("return_date", "date"), ("quantity", "int"), ("status", "status"),
    ], [("supply_item_id", "supply_items")]),

    ("inventory_movements", [
        ("movement_date", "date"), ("quantity", "int"), ("direction", "direction"),
    ], [("warehouse_id", "warehouses")]),

    ("transport_routes", [
        ("route_code", "code"), ("city_from", "city"), ("city_to", "city"),
        ("distance_km", "int"), ("transport_mode", "transport_mode"),
    ], []),

    ("customs_declarations", [
        ("customs_declaration_number", "code"),
        ("customs_clearance_date", "date"), ("customs_duty", "money"),
        ("country_origin", "country"), ("country_destination", "country"),
    ], [("shipment_id", "shipments")]),

    ("supplier_ratings", [
        ("rating", "float"), ("quality_grade", "quality_grade"),
        ("created_at", "datetime"),
    ], [("supplier_id", "suppliers")]),
]


# ---------- Утилиты ----------
def singular(t: str) -> str:
    if t.endswith("ies"): return t[:-3] + "y"
    if t.endswith("s"):   return t[:-1]
    return t


def gen_value(kind: str, rng: random.Random):
    if kind == "direction":
        return rng.choice(DIRECTIONS)
    if kind == "code":
        prefix = rng.choice(["CTR","INV","WBL","TTN","PL","CD","BAT","SN","SKU",
                             "GTIN","UPC","EAN","HS","SEAL","CONT","TRL","RT",
                             "WH","DOCK","TRK","SUP","BUY","PRD","PO","SO",
                             "DN","PRO","BOL","AWB"])
        return f"{prefix}-{rng.randint(10**6, 10**7 - 1)}"
    if kind == "date":
        return (datetime.utcnow() - timedelta(days=rng.randint(0, 730))).strftime("%Y-%m-%d")
    if kind == "datetime":
        return (datetime.utcnow() - timedelta(
            days=rng.randint(0, 730), hours=rng.randint(0, 23),
            minutes=rng.randint(0, 59), seconds=rng.randint(0, 59)
        )).strftime("%Y-%m-%d %H:%M:%S")
    if kind == "money":    return round(rng.uniform(10, 500000), 2)
    if kind == "int":      return rng.randint(1, 100000)
    if kind == "float":    return round(rng.uniform(0, 10000), 2)
    if kind == "name":     return f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
    if kind == "product":  return f"{rng.choice(PRODUCTS)} #{rng.randint(1, 999)}"
    if kind == "category": return rng.choice(CATEGORIES)
    if kind == "subcategory": return rng.choice(SUBCATEGORIES)
    if kind == "brand":    return rng.choice(BRANDS)
    if kind == "model":    return f"{rng.choice(['X','Y','Z','A','B','C'])}{rng.randint(100, 9999)}"
    if kind == "country":  return rng.choice(COUNTRIES)
    if kind == "city":     return rng.choice(CITIES)
    if kind == "region":   return rng.choice(REGIONS)
    if kind == "bool":     return rng.choice([True, False])
    if kind == "coord":    return round(rng.uniform(-180, 180), 6)
    if kind == "text":     return f"Note {rng.randint(1, 10000)}"
    if kind == "email":    return f"contact{rng.randint(1, 9999)}@example.com"
    if kind == "phone":    return f"+7{rng.randint(900_000_0000, 999_999_9999)}"
    if kind == "url":      return f"https://example.com/track/{rng.randint(10**6, 10**7 - 1)}"
    if kind in ENUM_VALUES: return rng.choice(ENUM_VALUES[kind])
    return ""


def rows_to_csv_bytes(rows, columns) -> bytes:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=columns)
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue().encode("utf-8")


# ---------- S3 ----------
def make_s3_client():
    return boto3.client(
        "s3", endpoint_url=S3_ENDPOINT,
        aws_access_key_id=S3_ACCESS_KEY, aws_secret_access_key=S3_SECRET_KEY,
        region_name=S3_REGION,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def ensure_bucket(s3, bucket):
    try:
        s3.head_bucket(Bucket=bucket); print(f"  ✓ Bucket '{bucket}' уже есть")
    except ClientError:
        s3.create_bucket(Bucket=bucket); print(f"  + Создан bucket '{bucket}'")


def clean_prefix(s3, prefix: str) -> int:
    """Удаляет все объекты под префиксом. Возвращает количество удалённых."""
    deleted = 0
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=prefix):
        contents = page.get("Contents", [])
        if not contents:
            continue
        # Удаляем пачками по 1000 (лимит S3 delete_objects)
        for i in range(0, len(contents), 1000):
            batch = contents[i:i + 1000]
            s3.delete_objects(
                Bucket=S3_BUCKET,
                Delete={"Objects": [{"Key": o["Key"]} for o in batch]},
            )
            deleted += len(batch)
    return deleted


# ---------- Загрузка таблицы ----------
def pick_columns(table_name, core, fks, rng):
    reserved = {f"{singular(table_name)}_id"} | {f[0] for f in fks} | {c[0] for c in core}
    available = [c for c in COLUMN_POOL if c[0] not in reserved]
    n_extra = max(0, COLUMNS_PER_TABLE - len(core))
    extra = rng.sample(available, min(n_extra, len(available)))
    return core + extra


def upload_table(s3, table_name, picked, fks, rows_count):
    pk = f"{singular(table_name)}_id"
    all_columns = [pk] + [c for c, _ in picked] + [fk for fk, _ in fks]
    all_columns = list(dict.fromkeys(all_columns))

    # ---- Дедупликация: чистим префикс stg/{table}/ ----
    if CLEAN_BEFORE_UPLOAD:
        prefix = f"{LAYER}/{table_name}/"
        n = clean_prefix(s3, prefix)
        if n:
            print(f"    🧹 очищено {n} старых объектов под {prefix}")

    rng = random.Random(f"{RANDOM_SEED}-{table_name}")
    total_bytes = 0
    part_num = 0

    for start in range(0, rows_count, CHUNK_SIZE):
        part_num += 1
        end = min(start + CHUNK_SIZE, rows_count)
        chunk = []
        for i in range(start + 1, end + 1):
            row = {pk: i}
            for fk_name, _ in fks:
                row[fk_name] = rng.randint(1, ROWS)
            for col_name, kind in picked:
                row[col_name] = gen_value(kind, rng)
            chunk.append(row)

        payload = rows_to_csv_bytes(chunk, all_columns)
        key = f"{LAYER}/{table_name}/{PARTITION_DATE}/{table_name}_part_{part_num:03d}.csv"
        s3.put_object(Bucket=S3_BUCKET, Key=key, Body=payload, ContentType="text/csv")
        total_bytes += len(payload)
        print(f"    → s3://{S3_BUCKET}/{key} ({len(chunk)} строк, {len(payload)/1024:.1f} KB)")

    print(f"  ✓ {table_name}: {rows_count} строк, {len(all_columns)} колонок, "
          f"{total_bytes/1024/1024:.2f} MB")
    return all_columns


# ---------- dbt-модели ----------
def write_dbt_models(tables_columns):
    models_dir = DBT_PROJECT_DIR / "models" / "staging"
    models_dir.mkdir(parents=True, exist_ok=True)

    for old in models_dir.glob("stg_*.sql"):
        old.unlink()
    for old in models_dir.glob("sources.yml"):
        old.unlink()

    for table_name in tables_columns:
        sql = ("{{ config(materialized='view') }}\n\n"
               "SELECT *\n"
               f"FROM {{{{ source('raw', 'raw_{table_name}') }}}}\n")
        (models_dir / f"stg_{table_name}.sql").write_text(sql, encoding="utf-8")

    sources = "version: 2\n\nsources:\n  - name: raw\n    schema: analytics\n    tables:\n"
    for table_name in tables_columns:
        sources += f"      - name: raw_{table_name}\n"
    (models_dir / "sources.yml").write_text(sources, encoding="utf-8")

    print(f"  ✓ Сгенерировано {len(tables_columns)} dbt-моделей в {models_dir}")
    print(f"  ✓ Обновлён sources.yml")


# ---------- Main ----------
def main():
    print(f"Генерация {len(TABLES)} stg-таблиц по ~{COLUMNS_PER_TABLE} колонок")
    print(f"  ROWS={ROWS}, CHUNK_SIZE={CHUNK_SIZE}, seed={RANDOM_SEED}")
    print(f"  S3: {S3_ENDPOINT}, bucket={S3_BUCKET}, layer={LAYER}, partition={PARTITION_DATE}")
    print(f"  Очистка перед загрузкой: {'ВКЛ' if CLEAN_BEFORE_UPLOAD else 'ВЫКЛ'}\n")

    s3 = make_s3_client()
    ensure_bucket(s3, S3_BUCKET)
    print()

    tables_columns = {}
    tables_types = {}

    for table_name, core, fks in TABLES:
        pk = f"{singular(table_name)}_id"
        rng_cols = random.Random(f"{RANDOM_SEED}-cols-{table_name}")
        picked = pick_columns(table_name, core, fks, rng_cols)
        total_cols = len(picked) + 1 + len(fks)

        print(f">>> {table_name}  ({total_cols} колонок)")
        cols = upload_table(s3, table_name, picked, fks, ROWS)
        tables_columns[table_name] = cols

        col_types = [(pk, "INTEGER")]
        for col_name, kind in picked:
            col_types.append((col_name, KIND_TO_PG.get(kind, "TEXT")))
        for fk_name, _ in fks:
            col_types.append((fk_name, "INTEGER"))
        tables_types[table_name] = col_types
        print()

    schema = {t: {"columns": tables_types[t]} for t in tables_types}
    SCHEMA_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCHEMA_JSON_PATH.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ✓ Схема сохранена: {SCHEMA_JSON_PATH}\n")

    write_dbt_models(tables_columns)

    print(f"\n✅ Готово! {len(TABLES)} таблиц загружено в S3, "
          f"{len(dbt_tables := tables_columns)} dbt-моделей сгенерировано.")


if __name__ == "__main__":
    main()