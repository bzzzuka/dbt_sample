{{ config(materialized='table', format='PARQUET') }}

SELECT
    c.category_id,
    c.category_name,
    c.department,
    COUNT(DISTINCT i.order_id) AS orders_count,
    SUM(i.quantity)            AS units_sold,
    SUM(i.line_total)          AS revenue,
    ROUND(
        SUM(i.line_total) * 100.0
        / (SELECT SUM(line_total) FROM {{ ref('stg_retail__order_items') }}),
        2
    ) AS revenue_share_pct
FROM {{ ref('stg_retail__order_items') }} i
JOIN {{ ref('stg_retail__products') }} p
    ON p.product_id = i.product_id
JOIN {{ ref('stg_retail__categories') }} c
    ON c.category_id = p.category_id
GROUP BY c.category_id, c.category_name, c.department
