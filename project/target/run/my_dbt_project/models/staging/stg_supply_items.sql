
  create view "dbt_db"."public"."stg_supply_items__dbt_tmp"
    
    
  as (
    

SELECT * FROM "dbt_db"."public"."raw_supply_items"
  );