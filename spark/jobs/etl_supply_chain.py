"""
Spark ETL: CSV из MinIO -> Iceberg-таблица в MinIO.

Читает все CSV-файлы таблицы suppliers из S3 (MinIO),
пишет в Iceberg-таблицу lakehouse.supply_chain.suppliers.

Запуск:
    docker exec spark_iceberg spark-submit /opt/spark/jobs/etl_supply_chain.py
"""

from pyspark.sql import SparkSession


def main():
    spark = (
        SparkSession.builder
        .appName("etl_supply_chain")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")

    print("=" * 60)
    print("  Spark ETL -> Iceberg")
    print("=" * 60)

    # 1. Создаём namespace (базу данных) в Iceberg
    print("\n[1] Создаём namespace lakehouse.supply_chain...")
    spark.sql("CREATE NAMESPACE IF NOT EXISTS lakehouse.supply_chain")
    spark.sql("SHOW NAMESPACES IN lakehouse").show()

    # 2. Читаем CSV из MinIO
    print("\n[2] Читаем CSV suppliers из MinIO...")
    csv_path = "s3a://dbt-bucket/stg/suppliers/*/*.csv"
    df = (
        spark.read
        .option("header", "true")
        .option("inferSchema", "true")
        .csv(csv_path)
    )

    rows = df.count()
    cols = len(df.columns)
    print(f"    Прочитано: {rows} строк, {cols} колонок")
    print("    Схема (первые 5 полей):")
    for field in df.schema.fields[:5]:
        print(f"      - {field.name}: {field.dataType}")

    # 3. Пишем в Iceberg (createOrReplace — пересоздаёт таблицу)
    print("\n[3] Пишем в Iceberg: lakehouse.supply_chain.suppliers...")
    (
        df.writeTo("lakehouse.supply_chain.suppliers")
        .createOrReplace()
    )

    # 4. Проверяем
    print("\n[4] Проверка:")
    spark.sql("SELECT COUNT(*) AS total FROM lakehouse.supply_chain.suppliers").show()
    spark.sql("SELECT * FROM lakehouse.supply_chain.suppliers LIMIT 3").show(truncate=False)

    # 5. Показываем список таблиц
    print("\n[5] Таблицы в namespace lakehouse.supply_chain:")
    spark.sql("SHOW TABLES IN lakehouse.supply_chain").show()

    print("\n✅ Готово. Iceberg-таблица создана.")
    spark.stop()


if __name__ == "__main__":
    main()