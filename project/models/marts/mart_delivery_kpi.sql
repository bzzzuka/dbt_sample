{{ config(materialized='table') }}

WITH shipments AS (
    SELECT
        s.shipment_id,
        s.supply_order_id,
        s.ship_date,
        s.delivery_date,
        s.transport_mode,
        s.container_type,
        s.weight_kg,
        s.shipping_cost,
        s.status,
        -- срок доставки в днях
        (s.delivery_date - s.ship_date) AS delivery_days,
        o.priority
    FROM {{ ref('stg_shipments') }} s
    LEFT JOIN {{ ref('stg_supply_orders') }} o USING (supply_order_id)
)
SELECT
    transport_mode,
    container_type,
    priority,
    COUNT(*)                                        AS shipments_count,
    SUM(weight_kg)                                  AS total_weight_kg,
    SUM(shipping_cost)                              AS total_shipping_cost,
    AVG(shipping_cost)                              AS avg_shipping_cost,
    AVG(delivery_days)                              AS avg_delivery_days,
    MIN(delivery_days)                              AS min_delivery_days,
    MAX(delivery_days)                              AS max_delivery_days,
    COUNT(*) FILTER (WHERE status = 'delivered')    AS delivered_count,
    COUNT(*) FILTER (WHERE status = 'cancelled')    AS cancelled_count,
    COUNT(*) FILTER (WHERE status = 'returned')     AS returned_count
FROM shipments
GROUP BY transport_mode, container_type, priority