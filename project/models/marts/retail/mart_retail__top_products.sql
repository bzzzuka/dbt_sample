{{ config(
    materialized='table',
    engine='OLAP',
    keys=['product_id'],
    table_type='PRIMARY',
    distributed_by=['product_id'],
    buckets=4,
    properties='{"replication_num": "1"}'
) }}

SELECT
    p.product_id,
    p.product_name,
    c.category_name,
    p.brand,
    COUNT(DISTINCT i.order_id) AS orders_count,
    SUM(i.quantity)            AS units_sold,
    SUM(i.line_total)          AS revenue,
    AVG(i.unit_price)          AS avg_unit_price
FROM {{ ref('stg_retail__order_items') }} i
JOIN {{ ref('stg_retail__products') }} p
    ON p.product_id = i.product_id
JOIN {{ ref('stg_retail__categories') }} c
    ON c.category_id = p.category_id
GROUP BY p.product_id, p.product_name, c.category_name, p.brand
