{{ config(materialized='view') }}

SELECT
    event_id,
    customer_id,
    product_id,
    event_type,
    device,
    channel,
    event_time::timestamp AS event_time,
    session_id
FROM {{ source('raw', 'raw_events') }}