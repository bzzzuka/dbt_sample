
  
    

  create table `analytics`.`mart_delivery_kpi__dbt_tmp`
      PRIMARY KEY (transport_mode,container_type,priority)
    DISTRIBUTED BY HASH (transport_mode) BUCKETS 4
    PROPERTIES (
      "replication_num" = "1"
    )
  as 

WITH shipments AS (
    SELECT
        s.shipment_id,
        s.supply_order_id,
        s.ship_date,
        s.delivery_date,
        COALESCE(s.transport_mode, 'unknown')    AS transport_mode,
        COALESCE(s.container_type, 'unknown')    AS container_type,
        COALESCE(o.priority, 'unknown')          AS priority,
        s.weight_kg,
        s.shipping_cost,
        s.status,
        DATEDIFF(s.delivery_date, s.ship_date)   AS delivery_days
    FROM `analytics`.`stg_shipments` s
    LEFT JOIN `analytics`.`stg_supply_orders` o
        ON o.supply_order_id = s.supply_order_id
)
SELECT
    transport_mode,
    container_type,
    priority,
    COUNT(*)                                          AS shipments_count,
    SUM(weight_kg)                                    AS total_weight_kg,
    SUM(shipping_cost)                                AS total_shipping_cost,
    AVG(shipping_cost)                                AS avg_shipping_cost,
    AVG(delivery_days)                                AS avg_delivery_days,
    MIN(delivery_days)                                AS min_delivery_days,
    MAX(delivery_days)                                AS max_delivery_days,
    COUNT(CASE WHEN status = 'delivered' THEN 1 END)  AS delivered_count,
    COUNT(CASE WHEN status = 'cancelled' THEN 1 END)  AS cancelled_count,
    COUNT(CASE WHEN status = 'returned' THEN 1 END)   AS returned_count
FROM shipments
GROUP BY transport_mode, container_type, priority
  