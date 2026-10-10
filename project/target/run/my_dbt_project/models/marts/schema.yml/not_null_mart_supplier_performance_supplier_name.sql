select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
    



select supplier_name
from "dbt_db"."public"."mart_supplier_performance"
where supplier_name is null



      
    ) dbt_internal_test