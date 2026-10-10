
    
    

select
    warehouse_id as unique_field,
    count(*) as n_records

from "dbt_db"."public"."mart_warehouse_activity"
where warehouse_id is not null
group by warehouse_id
having count(*) > 1


