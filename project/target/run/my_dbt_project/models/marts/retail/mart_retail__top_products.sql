
  
    

  create table `analytics`.`mart_retail__top_products__dbt_tmp`
      PRIMARY KEY (product_id)
    DISTRIBUTED BY HASH (product_id) BUCKETS 4
    PROPERTIES (
      "replication_num" = "1"
    )
  as 

SELECT
    p.product_id,
    p.product_name,
    c.category_name,
    p.brand,
    COUNT(DISTINCT i.order_id) AS orders_count,
    SUM(i.quantity)            AS units_sold,
    SUM(i.line_total)          AS revenue,
    AVG(i.unit_price)          AS avg_unit_price
FROM `analytics`.`stg_retail__order_items` i
JOIN `analytics`.`stg_retail__products` p
    ON p.product_id = i.product_id
JOIN `analytics`.`stg_retail__categories` c
    ON c.category_id = p.category_id
GROUP BY p.product_id, p.product_name, c.category_name, p.brand
  