import os
import sys
import logging
from datetime import datetime, timedelta
import requests
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
if os.path.exists(env_path):
    load_dotenv(env_path)

BINANCE_REST_BASE = os.getenv('BINANCE_REST_BASE', 'https://api.binance.com')
SYMBOLS = os.getenv('BINANCE_SYMBOLS', 'btcusdt,ethusdt,bnbusdt').split(',')

PG_HOST = os.getenv('POSTGRES_HOST', 'postgres')
if "postgres" in PG_HOST and not os.environ.get("RUNNING_IN_DOCKER"):
    PG_HOST = "localhost"
PG_PORT = os.getenv('POSTGRES_PORT', '5432')
PG_USER = os.getenv('POSTGRES_USER', 'postgres')
PG_PASS = os.getenv('POSTGRES_PASSWORD', 'postgres')
PG_DB = os.getenv('POSTGRES_ANALYTICS_DB', 'crypto_analytics')

def get_db_connection():
    return psycopg2.connect(
        host=PG_HOST, port=PG_PORT, user=PG_USER, password=PG_PASS, dbname=PG_DB
    )

def fetch_klines_chunk(symbol, interval, start_time_ms, end_time_ms, limit=1000):
    """Fetch a chunk of klines from Binance REST API"""
    url = f"{BINANCE_REST_BASE}/api/v3/klines"
    params = {
        'symbol': symbol.upper(),
        'interval': interval,
        'startTime': start_time_ms,
        'endTime': end_time_ms,
        'limit': limit
    }
    
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()

def insert_klines_to_pg(pg_conn, symbol, klines):
    """Insert or update kline records in Postgres"""
    if not klines:
        return 0
        
    records = []
    for k in klines:
        # Binance kline output format:
        # [0] Open time
        # [1] Open
        # [2] High
        # [3] Low
        # [4] Close
        # [5] Volume
        # [6] Close time
        # [7] Quote asset volume
        # [8] Number of trades
        # [9] Taker buy base asset volume
        # [10] Taker buy quote asset volume
        # [11] Ignore
        
        open_time = datetime.utcfromtimestamp(k[0] / 1000.0)
        close_time = datetime.utcfromtimestamp(k[6] / 1000.0)
        
        records.append((
            symbol.upper(),
            open_time,
            float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5]),
            close_time,
            float(k[7]), int(k[8]), float(k[9]), float(k[10])
        ))

    upsert_query = """
        INSERT INTO raw_klines 
        (symbol, open_time, open, high, low, close, volume, close_time, quote_volume, trade_count, taker_buy_base_volume, taker_buy_quote_volume)
        VALUES %s
        ON CONFLICT (symbol, open_time) DO UPDATE SET
            high = EXCLUDED.high,
            low = EXCLUDED.low,
            close = EXCLUDED.close,
            volume = EXCLUDED.volume,
            close_time = EXCLUDED.close_time,
            quote_volume = EXCLUDED.quote_volume,
            trade_count = EXCLUDED.trade_count,
            taker_buy_base_volume = EXCLUDED.taker_buy_base_volume,
            taker_buy_quote_volume = EXCLUDED.taker_buy_quote_volume,
            ingested_at = NOW();
    """
    
    try:
        with pg_conn.cursor() as cur:
            execute_values(cur, upsert_query, records)
        pg_conn.commit()
        return len(records)
    except Exception as e:
        logger.error(f"Failed to insert klines for {symbol}: {e}")
        pg_conn.rollback()
        return 0

def backfill_symbol(pg_conn, symbol, days_back=7):
    """Fetch and insert historical klines for the past N days"""
    end_dt = datetime.utcnow()
    start_dt = end_dt - timedelta(days=days_back)
    
    start_ms = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)
    
    logger.info(f"Starting backfill for {symbol.upper()} from {start_dt} to {end_dt}")
    
    current_ms = start_ms
    total_inserted = 0
    
    while current_ms < end_ms:
        try:
            # Fetch 1000 candles at a time (Binance limit)
            # 1000 minutes = 16.6 hours
            chunk_end_ms = min(end_ms, current_ms + (1000 * 60 * 1000))
            
            klines = fetch_klines_chunk(symbol, '1m', current_ms, chunk_end_ms)
            
            if not klines:
                logger.info(f"No more data found for {symbol.upper()} after {datetime.utcfromtimestamp(current_ms/1000.0)}")
                break
                
            inserted = insert_klines_to_pg(pg_conn, symbol, klines)
            total_inserted += inserted
            
            # Update current_ms to the end of the fetched chunk + 1ms to avoid overlap
            current_ms = klines[-1][0] + 1
            
            # Respect rate limits
            sys.stdout.write(f"\r{symbol.upper()}: Inserted {total_inserted} records... ")
            sys.stdout.flush()
            
        except Exception as e:
            logger.error(f"Error fetching data for {symbol.upper()}: {e}")
            break
            
    print() # Newline after progress bar
    logger.info(f"Finished backfill for {symbol.upper()}. Total inserted: {total_inserted}")

if __name__ == "__main__":
    # Can quickly pass env var DAYS_BACK to set history length (default 2 for lightweight testing)
    days_back = int(os.getenv('DAYS_BACK', '2'))
    
    try:
        conn = get_db_connection()
        logger.info(f"Connected to Postgres at {PG_HOST}")
        
        for sym in SYMBOLS:
            backfill_symbol(conn, sym, days_back=days_back)
            
        conn.close()
        logger.info("Historical data ingestion complete.")
        
    except Exception as e:
        logger.error(f"Initialization failed: {e}")
