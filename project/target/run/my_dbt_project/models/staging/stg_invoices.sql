
  create view `analytics`.`stg_invoices__dbt_tmp` as 

SELECT *
FROM `analytics`.`raw_invoices`;