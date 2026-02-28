-- =============================================================================
-- PostgreSQL Initialization Script 2: Create Schema in crypto_analytics DB
-- Run as: psql -U postgres -d crypto_analytics -f this_file.sql
-- =============================================================================

\c crypto_analytics;

-- ---------------------------------------------------------------------------
-- Raw historical klines (candles) from Binance REST API
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS raw_klines (
    id              BIGSERIAL PRIMARY KEY,
    symbol          VARCHAR(20)     NOT NULL,
    open_time       TIMESTAMPTZ     NOT NULL,
    open            NUMERIC(20, 8)  NOT NULL,
    high            NUMERIC(20, 8)  NOT NULL,
    low             NUMERIC(20, 8)  NOT NULL,
    close           NUMERIC(20, 8)  NOT NULL,
    volume          NUMERIC(30, 8)  NOT NULL,
    close_time      TIMESTAMPTZ     NOT NULL,
    quote_volume    NUMERIC(30, 8),
    trade_count     INTEGER,
    taker_buy_base_volume   NUMERIC(30, 8),
    taker_buy_quote_volume  NUMERIC(30, 8),
    ingested_at     TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    UNIQUE (symbol, open_time)
);

CREATE INDEX IF NOT EXISTS idx_raw_klines_symbol_time ON raw_klines (symbol, open_time DESC);

-- ---------------------------------------------------------------------------
-- Real-time 1-minute OHLCV aggregates from the Python streaming consumer
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fact_realtime_trades_1m (
    id              BIGSERIAL PRIMARY KEY,
    symbol          VARCHAR(20)     NOT NULL,
    minute_ts       TIMESTAMPTZ     NOT NULL,
    open            NUMERIC(20, 8)  NOT NULL,
    high            NUMERIC(20, 8)  NOT NULL,
    low             NUMERIC(20, 8)  NOT NULL,
    close           NUMERIC(20, 8)  NOT NULL,
    volume          NUMERIC(30, 8)  NOT NULL,
    trade_count     INTEGER         NOT NULL DEFAULT 0,
    vwap            NUMERIC(20, 8),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    UNIQUE (symbol, minute_ts)
);

CREATE INDEX IF NOT EXISTS idx_fact_rt_symbol_time ON fact_realtime_trades_1m (symbol, minute_ts DESC);
