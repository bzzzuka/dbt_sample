

SELECT
    order_id,
    customer_id,
    status,
    payment_method,
    total_amount::numeric(12,2) AS total_amount,
    currency,
    created_at::timestamp AS created_at,
    updated_at::timestamp AS updated_at,
    shipping_city,
    shipping_country
FROM "dbt_db"."public"."raw_orders"