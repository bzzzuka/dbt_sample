
  create view "dbt_db"."public"."stg_deliveries__dbt_tmp"
    
    
  as (
    

SELECT * FROM "dbt_db"."public"."raw_deliveries"
  );