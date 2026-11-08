select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
    



select category_id
from `analytics`.`mart_retail__sales_by_category`
where category_id is null



      
    ) dbt_internal_test