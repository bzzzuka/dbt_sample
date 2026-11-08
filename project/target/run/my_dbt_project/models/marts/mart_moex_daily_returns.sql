
  
    

  create table `analytics`.`mart_moex_daily_returns__dbt_tmp`
      PRIMARY KEY (ticker,tradedate)
    DISTRIBUTED BY HASH (ticker) BUCKETS 4
    PROPERTIES (
      "replication_num" = "1"
    )
  as 

SELECT
    ticker,
    tradedate,
    close,
    LAG(close) OVER (PARTITION BY ticker ORDER BY tradedate) AS prev_close,
    ROUND(
        (close - LAG(close) OVER (PARTITION BY ticker ORDER BY tradedate))
        / NULLIF(LAG(close) OVER (PARTITION BY ticker ORDER BY tradedate), 0) * 100,
        4
    ) AS daily_return_pct
FROM `analytics`.`stg_moex_prices`
  