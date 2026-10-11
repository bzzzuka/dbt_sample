
  
    

  create table `analytics`.`mart_supply_by_category__dbt_tmp`
      PRIMARY KEY (category)
    DISTRIBUTED BY HASH (category) BUCKETS 4
    PROPERTIES (
      "replication_num" = "1"
    )
  as 

SELECT
    i.category,
    COUNT(DISTINCT i.supply_order_id)          AS orders_count,
    COUNT(*)                                   AS items_count,
    SUM(i.quantity)                            AS total_quantity,
    SUM(i.total_price)                         AS total_revenue,
    AVG(i.unit_price)                          AS avg_unit_price,
    COUNT(DISTINCT i.unit_of_measure)          AS uom_variety
FROM `analytics`.`stg_supply_items` i
GROUP BY i.category
ORDER BY total_revenue DESC
  