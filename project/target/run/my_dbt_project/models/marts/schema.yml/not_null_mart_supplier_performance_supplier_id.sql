select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
    



select supplier_id
from `analytics`.`mart_supplier_performance`
where supplier_id is null



      
    ) dbt_internal_test