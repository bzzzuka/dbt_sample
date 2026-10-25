{{ config(materialized='view') }}

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
FROM {{ source('raw', 'raw_moex_prices') }}