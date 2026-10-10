
  create view "dbt_db"."public"."stg_warehouses__dbt_tmp"
    
    
  as (
    

SELECT * FROM "dbt_db"."public"."raw_warehouses"
  );