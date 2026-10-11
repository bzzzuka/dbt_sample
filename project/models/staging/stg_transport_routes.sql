{{ config(materialized='view') }}

SELECT *
FROM {{ source('raw', 'raw_transport_routes') }}
