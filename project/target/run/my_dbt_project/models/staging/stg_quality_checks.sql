
  create view "dbt_db"."public"."stg_quality_checks__dbt_tmp"
    
    
  as (
    

SELECT * FROM "dbt_db"."public"."raw_quality_checks"
  );