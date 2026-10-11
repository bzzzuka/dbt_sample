select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
    

select
    transport_mode as unique_field,
    count(*) as n_records

from `analytics`.`mart_transport_analysis`
where transport_mode is not null
group by transport_mode
having count(*) > 1



      
    ) dbt_internal_test