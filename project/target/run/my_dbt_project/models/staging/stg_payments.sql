
  create view "dbt_db"."public"."stg_payments__dbt_tmp"
    
    
  as (
    

SELECT * FROM "dbt_db"."public"."raw_payments"
  );