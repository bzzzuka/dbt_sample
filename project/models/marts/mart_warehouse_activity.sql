{{ config(
    materialized='table',
    engine='OLAP',
    keys=['warehouse_id'],
    table_type='PRIMARY',
    distributed_by=['warehouse_id'],
    buckets=4,
    properties={"replication_num": "1"}
) }}

WITH movements AS (
    SELECT
        warehouse_id,
        COUNT(*)                                        AS movements_count,
        SUM(quantity)                                   AS total_quantity,
        COUNT(CASE WHEN direction = 'in' THEN 1 END)     AS inbound_count,
        COUNT(CASE WHEN direction = 'out' THEN 1 END)    AS outbound_count,
        MIN(movement_date)                              AS first_movement,
        MAX(movement_date)                              AS last_movement
    FROM {{ ref('stg_inventory_movements') }}
    GROUP BY warehouse_id
),
deliveries AS (
    SELECT
        warehouse_id,
        COUNT(*)                                        AS deliveries_count,
        COUNT(CASE WHEN status = 'delivered' THEN 1 END) AS delivered_count,
        COUNT(CASE WHEN status = 'returned' THEN 1 END)  AS returned_count
    FROM {{ ref('stg_deliveries') }}
    GROUP BY warehouse_id
)
SELECT
    w.warehouse_id,
    w.warehouse_name,
    w.city,
    w.country,
    w.capacity_m3,
    COALESCE(m.movements_count, 0)    AS movements_count,
    COALESCE(m.total_quantity, 0)     AS total_quantity_moved,
    COALESCE(m.inbound_count, 0)      AS inbound_count,
    COALESCE(m.outbound_count, 0)     AS outbound_count,
    COALESCE(d.deliveries_count, 0)   AS deliveries_count,
    COALESCE(d.delivered_count, 0)    AS delivered_count,
    COALESCE(d.returned_count, 0)     AS returned_count,
    m.first_movement,
    m.last_movement
FROM {{ ref('stg_warehouses') }} w
LEFT JOIN movements  m USING (warehouse_id)
LEFT JOIN deliveries d USING (warehouse_id)
