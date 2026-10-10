

SELECT
    order_item_id,
    order_id,
    product_id,
    quantity,
    unit_price::numeric(12,2) AS unit_price,
    discount::numeric(5,2)    AS discount,
    line_total::numeric(12,2) AS line_total
FROM "dbt_db"."public"."raw_order_items"