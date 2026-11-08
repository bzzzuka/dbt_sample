select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
    



select month
from `analytics`.`mart_retail__sales_by_month`
where month is null



      
    ) dbt_internal_test