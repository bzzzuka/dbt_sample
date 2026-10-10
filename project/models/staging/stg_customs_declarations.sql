{{ config(materialized='view') }}

SELECT * FROM {{ source('raw', 'raw_customs_declarations') }}
