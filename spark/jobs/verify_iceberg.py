"""
Проверка Iceberg-каталога и таблиц, созданных Spark ETL.

Запуск:
    docker exec spark_iceberg /opt/spark/bin/spark-submit /opt/spark/jobs/verify_iceberg.py
"""

from pyspark.sql import SparkSession


def main():
    spark = (
        SparkSession.builder
        .appName("verify_iceberg")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")

    print("=" * 60)
    print("  Проверка Iceberg")
    print("=" * 60)

    print("\n[1] Каталоги:")
    spark.sql("SHOW CATALOGS").show(truncate=False)

    print("\n[2] Namespaces в lakehouse:")
    spark.sql("SHOW NAMESPACES IN lakehouse").show(truncate=False)

    print("\n[3] Таблицы в lakehouse.supply_chain:")
    spark.sql("SHOW TABLES IN lakehouse.supply_chain").show(truncate=False)

    print("\n[4] Данные lakehouse.supply_chain.suppliers:")
    spark.sql("SELECT * FROM lakehouse.supply_chain.suppliers LIMIT 5").show(truncate=False)

    spark.stop()


if __name__ == "__main__":
    main()
