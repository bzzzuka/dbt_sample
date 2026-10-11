select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
    



select warehouse_id
from `analytics`.`mart_warehouse_activity`
where warehouse_id is null



      
    ) dbt_internal_test