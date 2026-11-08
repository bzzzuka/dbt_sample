
  
    

  create table `analytics`.`mart_retail__sales_by_month__dbt_tmp`
      PRIMARY KEY (month)
    DISTRIBUTED BY HASH (month) BUCKETS 4
    PROPERTIES (
      "replication_num" = "1"
    )
  as 

WITH order_totals AS (
    SELECT
        DATE_FORMAT(order_date, '%Y-%m-01') AS month,
        COUNT(*)                            AS orders_count,
        SUM(subtotal)                       AS gross_revenue,
        SUM(discount_amount)                AS discount_amount,
        SUM(total_amount)                   AS net_revenue,
        AVG(total_amount)                   AS avg_order_value
    FROM `analytics`.`stg_retail__orders`
    GROUP BY 1
),
item_totals AS (
    SELECT
        DATE_FORMAT(o.order_date, '%Y-%m-01') AS month,
        COUNT(*)                              AS items_count,
        SUM(i.quantity)                       AS units_sold
    FROM `analytics`.`stg_retail__order_items` i
    JOIN `analytics`.`stg_retail__orders` o
        ON o.order_id = i.order_id
    GROUP BY 1
)
SELECT
    t.month,
    t.orders_count,
    COALESCE(i.items_count, 0) AS items_count,
    COALESCE(i.units_sold, 0)  AS units_sold,
    t.gross_revenue,
    t.discount_amount,
    t.net_revenue,
    t.avg_order_value
FROM order_totals t
LEFT JOIN item_totals i ON i.month = t.month
  