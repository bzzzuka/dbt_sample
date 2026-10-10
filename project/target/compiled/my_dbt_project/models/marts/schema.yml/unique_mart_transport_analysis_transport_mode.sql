
    
    

select
    transport_mode as unique_field,
    count(*) as n_records

from "dbt_db"."public"."mart_transport_analysis"
where transport_mode is not null
group by transport_mode
having count(*) > 1


