select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
    



select customer_id
from `analytics`.`mart_retail__customer_ltv`
where customer_id is null



      
    ) dbt_internal_test