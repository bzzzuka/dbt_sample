
    
    

select
    supplier_id as unique_field,
    count(*) as n_records

from "dbt_db"."public"."mart_supplier_performance"
where supplier_id is not null
group by supplier_id
having count(*) > 1


