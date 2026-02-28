{{ config(materialized='view') }}

WITH raw AS (
    SELECT
        id,
        symbol,
        minute_ts,
        open,
        high,
        low,
        close,
        volume,
        trade_count,
        vwap,
        updated_at AS ingested_at,
        'WS_STREAM' AS source_type
    FROM {{ source('crypto_raw', 'fact_realtime_trades_1m') }}
)

SELECT * FROM raw
