

SELECT
    customer_id,
    first_name,
    last_name,
    first_name || ' ' || last_name AS full_name,
    email,
    phone,
    city,
    country,
    created_at::timestamp AS created_at,
    is_active
FROM "dbt_db"."public"."raw_customers"