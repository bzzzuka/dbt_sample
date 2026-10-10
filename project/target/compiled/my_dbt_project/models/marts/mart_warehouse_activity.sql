

WITH movements AS (
    SELECT
        warehouse_id,
        COUNT(*)                                        AS movements_count,
        SUM(quantity)                                   AS total_quantity,
        COUNT(*) FILTER (WHERE direction = 'in')        AS inbound_count,
        COUNT(*) FILTER (WHERE direction = 'out')       AS outbound_count,
        MIN(movement_date)                              AS first_movement,
        MAX(movement_date)                              AS last_movement
    FROM "dbt_db"."public"."stg_inventory_movements"
    GROUP BY warehouse_id
),
deliveries AS (
    SELECT
        warehouse_id,
        COUNT(*)                                        AS deliveries_count,
        COUNT(*) FILTER (WHERE status = 'delivered')    AS delivered_count,
        COUNT(*) FILTER (WHERE status = 'returned')     AS returned_count
    FROM "dbt_db"."public"."stg_deliveries"
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
FROM "dbt_db"."public"."stg_warehouses" w
LEFT JOIN movements  m USING (warehouse_id)
LEFT JOIN deliveries d USING (warehouse_id)