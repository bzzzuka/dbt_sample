{{ config(materialized='view') }}

SELECT * FROM {{ source('retail_raw', 'raw_retail_promotions') }}
