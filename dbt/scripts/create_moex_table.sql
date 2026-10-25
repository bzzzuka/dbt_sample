-- Создание таблицы raw_moex_prices в StarRocks.
-- Запускать в StarRocks от root.

USE analytics;

CREATE TABLE IF NOT EXISTS raw_moex_prices (
    ticker      VARCHAR(20),
    tradedate   DATE,
    open        DECIMAL(15,2),
    high        DECIMAL(15,2),
    low         DECIMAL(15,2),
    close       DECIMAL(15,2),
    volume      BIGINT,
    value       DECIMAL(20,2),
    numtrades   BIGINT,
    boardid     VARCHAR(10)
)
ENGINE=OLAP
DUPLICATE KEY(ticker, tradedate)
DISTRIBUTED BY HASH(ticker) BUCKETS 4
PROPERTIES ("replication_num" = "1");