

WITH silver_1m AS (
    SELECT * FROM "crypto_analytics"."public_silver"."silver_klines_1m"
),

-- Generate 5-minute tumbling windows
time_buckets AS (
    SELECT
        symbol,
        date_trunc('hour', minute_ts) + 
        INTERVAL '5 min' * FLOOR(extract('minute' from minute_ts) / 5) AS bucket_5m,
        minute_ts,
        open, high, low, close, volume, trade_count
    FROM silver_1m
),

aggregated AS (
    SELECT
        symbol,
        bucket_5m,
        MIN(minute_ts) as first_minute,
        MAX(minute_ts) as last_minute,
        MAX(high) as high,
        MIN(low) as low,
        SUM(volume) as volume,
        SUM(trade_count) as trade_count
    FROM time_buckets
    GROUP BY symbol, bucket_5m
),

-- To get correct Open and Close, we join back to get the rows corresponding to first/last minute
final_calc AS (
    SELECT 
        a.symbol,
        a.bucket_5m,
        o.open AS open,
        a.high,
        a.low,
        c.close AS close,
        a.volume,
        a.trade_count
    FROM aggregated a
    JOIN time_buckets o ON a.symbol = o.symbol AND a.first_minute = o.minute_ts
    JOIN time_buckets c ON a.symbol = c.symbol AND a.last_minute = c.minute_ts
)

SELECT * FROM final_calc
ORDER BY bucket_5m DESC, symbol