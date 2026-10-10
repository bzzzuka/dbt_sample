{{ config(materialized='table') }}

SELECT
    p.product_id,
    p.product_name,
    p.category,
    p.brand,
    SUM(oi.quantity)                    AS units_sold,
    SUM(oi.line_total)                  AS revenue,
    COUNT(DISTINCT oi.order_id)         AS orders_count
FROM {{ ref('stg_order_items') }} oi
JOIN {{ ref('stg_products') }} p USING (product_id)
GROUP BY 1, 2, 3, 4