

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
    FROM "crypto_analytics"."public"."fact_realtime_trades_1m"
)

SELECT * FROM raw