
  create view "dbt_db"."public"."stg_products__dbt_tmp"
    
    
  as (
    

SELECT
    product_id,
    sku,
    name           AS product_name,
    category,
    subcategory,
    brand,
    price::numeric(12,2) AS price,
    cost::numeric(12,2)  AS cost,
    stock_quantity,
    created_at::timestamp AS created_at
FROM "dbt_db"."public"."raw_products"
  );