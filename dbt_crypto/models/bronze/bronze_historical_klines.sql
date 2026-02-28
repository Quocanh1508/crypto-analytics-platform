{{ config(materialized='view') }}

WITH raw AS (
    SELECT
        id,
        symbol,
        open_time AS minute_ts,
        open,
        high,
        low,
        close,
        volume,
        trade_count,
        close_time,
        quote_volume,
        taker_buy_base_volume,
        taker_buy_quote_volume,
        ingested_at,
        'REST_BATCH' AS source_type
    FROM {{ source('crypto_raw', 'raw_klines') }}
)

SELECT * FROM raw
