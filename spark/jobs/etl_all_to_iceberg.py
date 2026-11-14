"""
Full migration ingestion: all supply-chain and retail CSV -> Iceberg.

Source:
  s3a://dbt-bucket/stg/{table}/*/*.csv
  s3a://dbt-bucket/retail/stg/{table}/*/*.csv

Target:
  lakehouse.analytics.raw_{table}
  lakehouse.analytics.raw_retail_{table}
"""

from pyspark.sql import SparkSession

CATALOG = "lakehouse"
NAMESPACE = "analytics"
SUPPLY_BUCKET = "s3a://dbt-bucket/stg"
RETAIL_BUCKET = "s3a://dbt-bucket/retail/stg"

SUPPLY_TABLES = [
    "suppliers",
    "supply_contracts",
    "supply_orders",
    "supply_items",
    "shipments",
    "warehouses",
    "deliveries",
    "invoices",
    "payments",
    "quality_checks",
    "returns",
    "inventory_movements",
    "transport_routes",
    "customs_declarations",
    "supplier_ratings",
]

RETAIL_TABLES = [
    "categories",
    "products",
    "customers",
    "stores",
    "promotions",
    "orders",
    "order_items",
    "payments",
    "shipments",
    "returns",
    "reviews",
]


def load_table(spark, source_path: str, target: str):
    print(f"[read] {source_path}")
    df = (
        spark.read
        .option("header", "true")
        .option("inferSchema", "true")
        .csv(source_path)
    )
    rows = df.count()
    print(f"[write] {target}: {rows} rows, {len(df.columns)} columns")
    df.writeTo(target).createOrReplace()
    actual = spark.table(target).count()
    print(f"[ok] {target}: {actual} rows")


def main():
    spark = (
        SparkSession.builder
        .appName("all_tables_to_iceberg")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")
    spark.sql(f"CREATE NAMESPACE IF NOT EXISTS {CATALOG}.{NAMESPACE}")

    for table in SUPPLY_TABLES:
        load_table(
            spark,
            f"{SUPPLY_BUCKET}/{table}/*/*.csv",
            f"{CATALOG}.{NAMESPACE}.raw_{table}",
        )

    for table in RETAIL_TABLES:
        load_table(
            spark,
            f"{RETAIL_BUCKET}/{table}/*/*.csv",
            f"{CATALOG}.{NAMESPACE}.raw_retail_{table}",
        )

    print("[done] all supply and retail tables loaded to Iceberg")
    spark.stop()


if __name__ == "__main__":
    main()
