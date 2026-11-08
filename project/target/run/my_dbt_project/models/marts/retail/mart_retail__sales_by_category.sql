
  
    

  create table `analytics`.`mart_retail__sales_by_category__dbt_tmp`
      PRIMARY KEY (category_id)
    DISTRIBUTED BY HASH (category_id) BUCKETS 4
    PROPERTIES (
      "replication_num" = "1"
    )
  as 

SELECT
    c.category_id,
    c.category_name,
    c.department,
    COUNT(DISTINCT i.order_id) AS orders_count,
    SUM(i.quantity)            AS units_sold,
    SUM(i.line_total)          AS revenue,
    ROUND(
        SUM(i.line_total) * 100.0
        / (SELECT SUM(line_total) FROM `analytics`.`stg_retail__order_items`),
        2
    ) AS revenue_share_pct
FROM `analytics`.`stg_retail__order_items` i
JOIN `analytics`.`stg_retail__products` p
    ON p.product_id = i.product_id
JOIN `analytics`.`stg_retail__categories` c
    ON c.category_id = p.category_id
GROUP BY c.category_id, c.category_name, c.department
  