
    
    

select
    month as unique_field,
    count(*) as n_records

from `analytics`.`mart_retail__returns_rate`
where month is not null
group by month
having count(*) > 1


