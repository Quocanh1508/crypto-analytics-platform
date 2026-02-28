{{ config(
    materialized='incremental',
    unique_key=['symbol', 'minute_ts'],
    incremental_strategy='merge'
) }}

WITH historical AS (
    SELECT 
        symbol,
        minute_ts,
        open,
        high,
        low,
        close,
        volume,
        trade_count,
        source_type,
        ingested_at
    FROM {{ ref('bronze_historical_klines') }}
),

realtime AS (
    SELECT 
        symbol,
        minute_ts,
        open,
        high,
        low,
        close,
        volume,
        trade_count,
        source_type,
        ingested_at
    FROM {{ ref('bronze_realtime_klines') }}
),

-- Combine historical and real-time streams
combined AS (
    SELECT * FROM historical
    UNION ALL
    SELECT * FROM realtime
),

-- Deduplicate overlapping minutes (preferring real-time data which has VWAP and is frequently updated, or just taking the latest ingestion)
deduped AS (
    SELECT 
        *,
        ROW_NUMBER() OVER (
            PARTITION BY symbol, minute_ts 
            ORDER BY 
                CASE WHEN source_type = 'WS_STREAM' THEN 1 ELSE 2 END,
                ingested_at DESC
        ) as rn
    FROM combined
)

SELECT 
    symbol,
    minute_ts,
    open,
    high,
    low,
    close,
    volume,
    trade_count,
    source_type,
    ingested_at,
    CURRENT_TIMESTAMP AS dbt_updated_at
FROM deduped
WHERE rn = 1

{% if is_incremental() %}
    -- In incremental runs, only process data where the window is recent.
    -- We look back 2 hours to ensure late-arriving WS data or recent REST updates are caught.
    AND minute_ts >= (SELECT MAX(minute_ts) - INTERVAL '2 hours' FROM {{ this }})
{% endif %}
