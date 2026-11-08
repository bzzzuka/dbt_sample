{{ config(
    materialized='table',
    engine='OLAP',
    keys=['customer_id'],
    table_type='PRIMARY',
    distributed_by=['customer_id'],
    buckets=4,
    properties='{"replication_num": "1"}'
) }}

SELECT
    c.customer_id,
    CONCAT(c.first_name, ' ', c.last_name) AS customer_name,
    c.segment,
    c.loyalty_tier,
    c.country,
    COUNT(o.order_id)          AS orders_count,
    SUM(o.total_amount)        AS total_spent,
    AVG(o.total_amount)        AS avg_order_value,
    MIN(o.order_date)          AS first_order_date,
    MAX(o.order_date)          AS last_order_date
FROM {{ ref('stg_retail__customers') }} c
LEFT JOIN {{ ref('stg_retail__orders') }} o
    ON o.customer_id = c.customer_id
GROUP BY c.customer_id, c.first_name, c.last_name, c.segment, c.loyalty_tier, c.country
