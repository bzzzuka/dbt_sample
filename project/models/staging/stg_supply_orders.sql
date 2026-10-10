{{ config(materialized='view') }}

SELECT * FROM {{ source('raw', 'raw_supply_orders') }}
