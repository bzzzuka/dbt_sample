

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