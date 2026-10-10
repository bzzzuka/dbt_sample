
  create view "dbt_db"."public"."stg_supply_orders__dbt_tmp"
    
    
  as (
    

SELECT * FROM "dbt_db"."public"."raw_supply_orders"
  );