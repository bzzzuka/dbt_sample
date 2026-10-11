{{ config(
    materialized='table',
    engine='OLAP',
    keys=['category'],
    table_type='PRIMARY',
    distributed_by=['category'],
    buckets=4,
    properties={"replication_num": "1"}
) }}

SELECT
    i.category,
    COUNT(DISTINCT i.supply_order_id)          AS orders_count,
    COUNT(*)                                   AS items_count,
    SUM(i.quantity)                            AS total_quantity,
    SUM(i.total_price)                         AS total_revenue,
    AVG(i.unit_price)                          AS avg_unit_price,
    COUNT(DISTINCT i.unit_of_measure)          AS uom_variety
FROM {{ ref('stg_supply_items') }} i
GROUP BY i.category
ORDER BY total_revenue DESC
