{{ config(
    materialized='table',
    engine='OLAP',
    keys=['month'],
    table_type='PRIMARY',
    distributed_by=['month'],
    buckets=4,
    properties='{"replication_num": "1"}'
) }}

WITH orders_by_month AS (
    SELECT
        DATE_FORMAT(order_date, '%Y-%m-01') AS month,
        COUNT(*)                            AS orders_count
    FROM {{ ref('stg_retail__orders') }}
    GROUP BY 1
),
returns_by_month AS (
    SELECT
        DATE_FORMAT(return_date, '%Y-%m-01') AS month,
        COUNT(*)                             AS returns_count,
        SUM(refund_amount)                   AS refund_amount
    FROM {{ ref('stg_retail__returns') }}
    GROUP BY 1
)
SELECT
    o.month,
    o.orders_count,
    COALESCE(r.returns_count, 0) AS returns_count,
    COALESCE(r.refund_amount, 0) AS refund_amount,
    ROUND(COALESCE(r.returns_count, 0) / NULLIF(o.orders_count, 0) * 100, 2) AS return_rate_pct
FROM orders_by_month o
LEFT JOIN returns_by_month r ON r.month = o.month
