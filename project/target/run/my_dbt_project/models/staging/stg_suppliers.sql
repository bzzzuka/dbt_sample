
  create view "dbt_db"."public"."stg_suppliers__dbt_tmp"
    
    
  as (
    

SELECT * FROM "dbt_db"."public"."raw_suppliers"
  );