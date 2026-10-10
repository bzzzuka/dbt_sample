
  create view "dbt_db"."public"."stg_events__dbt_tmp"
    
    
  as (
    

SELECT
    event_id,
    customer_id,
    product_id,
    event_type,
    device,
    channel,
    event_time::timestamp AS event_time,
    session_id
FROM "dbt_db"."public"."raw_events"
  );