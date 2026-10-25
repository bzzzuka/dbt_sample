{{ config(
    materialized='table',
    engine='OLAP',
    keys=['ticker', 'tradedate'],
    table_type='PRIMARY',
    distributed_by=['ticker'],
    buckets=4,
    properties='{"replication_num": "1"}'
) }}

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
FROM {{ ref('stg_moex_prices') }}