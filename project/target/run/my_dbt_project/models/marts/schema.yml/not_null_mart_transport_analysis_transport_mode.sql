select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
    



select transport_mode
from "dbt_db"."public"."mart_transport_analysis"
where transport_mode is null



      
    ) dbt_internal_test