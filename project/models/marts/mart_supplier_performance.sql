{{ config(
    materialized='table',
    engine='OLAP',
    keys=['supplier_id'],
    table_type='PRIMARY',
    distributed_by=['supplier_id'],
    buckets=4,
    properties={"replication_num": "1"}
) }}

WITH supplier_orders AS (
    SELECT
        o.supplier_id,
        COUNT(*)              AS orders_count,
        SUM(o.total_price)    AS total_purchase_amount,
        AVG(o.total_price)    AS avg_order_amount,
        MIN(o.order_date)     AS first_order_date,
        MAX(o.order_date)     AS last_order_date
    FROM {{ ref('stg_supply_orders') }} o
    GROUP BY o.supplier_id
),
supplier_contracts AS (
    SELECT
        supplier_id,
        COUNT(*)           AS contracts_count,
        SUM(total_price)   AS contracts_total_amount
    FROM {{ ref('stg_supply_contracts') }}
    GROUP BY supplier_id
),
supplier_quality AS (
    SELECT
        s.supplier_id,
        AVG(sr.rating) AS avg_rating,
        COUNT(*)       AS ratings_count
    FROM {{ ref('stg_supplier_ratings') }} sr
    JOIN {{ ref('stg_suppliers') }} s ON s.supplier_id = sr.supplier_id
    GROUP BY s.supplier_id
)
SELECT
    s.supplier_id,
    s.supplier_name,
    s.country,
    s.city,
    s.region,
    s.rating                                  AS current_rating,
    COALESCE(sc.contracts_count, 0)           AS contracts_count,
    COALESCE(sc.contracts_total_amount, 0)    AS contracts_total_amount,
    COALESCE(so.orders_count, 0)              AS orders_count,
    COALESCE(so.total_purchase_amount, 0)     AS total_purchase_amount,
    COALESCE(so.avg_order_amount, 0)          AS avg_order_amount,
    so.first_order_date,
    so.last_order_date,
    COALESCE(sq.avg_rating, 0)                AS avg_quality_rating,
    COALESCE(sq.ratings_count, 0)             AS ratings_count
FROM {{ ref('stg_suppliers') }} s
LEFT JOIN supplier_contracts sc USING (supplier_id)
LEFT JOIN supplier_orders    so USING (supplier_id)
LEFT JOIN supplier_quality   sq USING (supplier_id)
