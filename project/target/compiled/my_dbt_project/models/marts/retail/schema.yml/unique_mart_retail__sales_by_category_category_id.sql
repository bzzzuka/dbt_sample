
    
    

select
    category_id as unique_field,
    count(*) as n_records

from `analytics`.`mart_retail__sales_by_category`
where category_id is not null
group by category_id
having count(*) > 1


