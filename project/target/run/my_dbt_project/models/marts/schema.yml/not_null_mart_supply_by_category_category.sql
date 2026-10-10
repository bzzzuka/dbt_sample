select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
    



select category
from "dbt_db"."public"."mart_supply_by_category"
where category is null



      
    ) dbt_internal_test