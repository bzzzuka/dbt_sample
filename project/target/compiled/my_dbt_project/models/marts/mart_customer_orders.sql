

SELECT
    c.customer_id,
    c.full_name,
    c.city,
    c.country,
    COUNT(o.order_id)                       AS orders_count,
    COALESCE(SUM(o.total_amount), 0)        AS total_spent,
    COALESCE(AVG(o.total_amount), 0)        AS avg_order_value,
    MIN(o.created_at)                       AS first_order_at,
    MAX(o.created_at)                       AS last_order_at
FROM "dbt_db"."public"."stg_customers" c
LEFT JOIN "dbt_db"."public"."stg_orders" o USING (customer_id)
GROUP BY 1, 2, 3, 4