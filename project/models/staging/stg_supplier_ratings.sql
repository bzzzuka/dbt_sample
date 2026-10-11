{{ config(materialized='view') }}

SELECT *
FROM {{ source('raw', 'raw_supplier_ratings') }}
