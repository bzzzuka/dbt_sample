{{ config(materialized='view') }}

SELECT *
FROM {{ source('raw', 'raw_quality_checks') }}
