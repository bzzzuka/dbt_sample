
  create view `analytics`.`stg_moex_prices__dbt_tmp` as 

SELECT
    ticker,
    tradedate,
    open,
    high,
    low,
    close,
    close - open AS change,
    ROUND((close - open) / NULLIF(open, 0) * 100, 2) AS change_pct,
    volume,
    value,
    numtrades,
    boardid
FROM `analytics`.`raw_moex_prices`;