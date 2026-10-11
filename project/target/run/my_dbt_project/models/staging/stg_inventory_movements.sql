
  create view `analytics`.`stg_inventory_movements__dbt_tmp` as 

SELECT *
FROM `analytics`.`raw_inventory_movements`;