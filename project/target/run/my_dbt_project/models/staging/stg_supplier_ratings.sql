
  create view "dbt_db"."public"."stg_supplier_ratings__dbt_tmp"
    
    
  as (
    

SELECT * FROM "dbt_db"."public"."raw_supplier_ratings"
  );