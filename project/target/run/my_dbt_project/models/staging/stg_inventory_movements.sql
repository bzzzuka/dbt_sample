
  create view "dbt_db"."public"."stg_inventory_movements__dbt_tmp"
    
    
  as (
    

SELECT * FROM "dbt_db"."public"."raw_inventory_movements"
  );