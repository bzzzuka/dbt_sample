-- Загрузка CSV MOEX из MinIO в StarRocks.
-- Замени {PARTITION_DATE} на свою дату.

USE analytics;

INSERT INTO raw_moex_prices
SELECT * FROM FILES(
    "path" = "s3://dbt-bucket/stg/moex_prices/{PARTITION_DATE}/moex_prices_part_001.csv",
    "format" = "csv",
    "csv.column_separator" = ",",
    "csv.row_delimiter" = "\n",
    "csv.skip_header" = "1",
    "aws.s3.endpoint" = "http://minio:9000",
    "aws.s3.access_key" = "minioadmin",
    "aws.s3.secret_key" = "minioadmin",
    "aws.s3.enable_ssl" = "false",
    "aws.s3.enable_path_style_access" = "true"
);