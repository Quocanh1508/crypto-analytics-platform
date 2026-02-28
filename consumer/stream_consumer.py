import os
import json
import logging
import time
from datetime import datetime
import psycopg2
from psycopg2.extras import execute_values
from kafka import KafkaConsumer
import boto3
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
if os.path.exists(env_path):
    load_dotenv(env_path)

KAFKA_BROKER = os.getenv('KAFKA_BROKER', 'localhost:9092')
if "kafka" in KAFKA_BROKER and not os.environ.get("RUNNING_IN_DOCKER"):
    KAFKA_BROKER = KAFKA_BROKER.replace("kafka", "localhost")

KAFKA_TOPIC = os.getenv('KAFKA_TOPIC_TRADES_RAW', 'crypto.trades.raw')

# Postgres config
PG_HOST = os.getenv('POSTGRES_HOST', 'postgres')
if "postgres" in PG_HOST and not os.environ.get("RUNNING_IN_DOCKER"):
    PG_HOST = "localhost"
PG_PORT = os.getenv('POSTGRES_PORT', '5432')
PG_USER = os.getenv('POSTGRES_USER', 'postgres')
PG_PASS = os.getenv('POSTGRES_PASSWORD', 'postgres')
PG_DB = os.getenv('POSTGRES_ANALYTICS_DB', 'crypto_analytics')

# MinIO config
MINIO_HOST = os.getenv('MINIO_HOST', 'minio')
if "minio" in MINIO_HOST and not os.environ.get("RUNNING_IN_DOCKER"):
    MINIO_HOST = "localhost"
MINIO_PORT = os.getenv('MINIO_PORT', '9000')
MINIO_USER = os.getenv('MINIO_ROOT_USER', 'minioadmin')
MINIO_PASS = os.getenv('MINIO_ROOT_PASSWORD', 'minioadmin')
MINIO_BUCKET = os.getenv('MINIO_BUCKET_RAW', 'raw')

# Buffers
raw_trades_buffer = []
candles_1m = {}  # { (symbol, minute_ms): { open, high, low, close, volume, count, quote_volume } }

# Thresholds
FLUSH_INTERVAL_SEC = 10
MAX_RAW_BUFFER_SIZE = 5000
last_flush_time = time.time()

def get_db_connection():
    return psycopg2.connect(
        host=PG_HOST, port=PG_PORT, user=PG_USER, password=PG_PASS, dbname=PG_DB
    )

def get_s3_client():
    return boto3.client('s3',
        endpoint_url=f"http://{MINIO_HOST}:{MINIO_PORT}",
        aws_access_key_id=MINIO_USER,
        aws_secret_access_key=MINIO_PASS,
        region_name='us-east-1'
    )

def flush_to_minio(s3_client):
    global raw_trades_buffer
    if not raw_trades_buffer:
        return
        
    trades_to_upload = raw_trades_buffer[:]
    raw_trades_buffer.clear()
    
    jsonl_str = "\n".join([json.dumps(t) for t in trades_to_upload])
    
    # File naming: crypto_trades/YYYY/MM/DD/HHMMSS_N.jsonl
    now = datetime.utcnow()
    date_path = now.strftime('%Y/%m/%d')
    file_name = now.strftime('%H%M%S') + f"_{len(trades_to_upload)}_trades.jsonl"
    object_key = f"crypto_trades/{date_path}/{file_name}"
    
    try:
        s3_client.put_object(
            Bucket=MINIO_BUCKET,
            Key=object_key,
            Body=jsonl_str.encode('utf-8'),
            ContentType='application/jsonl'
        )
        logger.info(f"Uploaded {len(trades_to_upload)} raw trades to MinIO: s3://{MINIO_BUCKET}/{object_key}")
    except Exception as e:
        logger.error(f"Failed to upload to MinIO: {e}")
        raw_trades_buffer.extend(trades_to_upload)

def flush_to_postgres(pg_conn):
    global candles_1m
    if not candles_1m:
        return
        
    records = []
    keys_to_delete = []
    now_ms = int(time.time() * 1000)
    
    for (symbol, minute_ms), c in candles_1m.items():
        minute_ts = datetime.utcfromtimestamp(minute_ms / 1000.0)
        updated_at = datetime.utcnow()
        vwap = c['quote_volume'] / c['volume'] if c['volume'] > 0 else c['close']
        
        records.append((
            symbol, minute_ts, c['open'], c['high'], c['low'], c['close'],
            c['volume'], c['trade_count'], vwap, updated_at
        ))
        
        # If the minute has passed by more than 65 seconds, remove from memory
        if now_ms > minute_ms + 65000:
            keys_to_delete.append((symbol, minute_ms))

    upsert_query = """
        INSERT INTO fact_realtime_trades_1m 
        (symbol, minute_ts, open, high, low, close, volume, trade_count, vwap, updated_at)
        VALUES %s
        ON CONFLICT (symbol, minute_ts) DO UPDATE SET
            high = GREATEST(fact_realtime_trades_1m.high, EXCLUDED.high),
            low = LEAST(fact_realtime_trades_1m.low, EXCLUDED.low),
            close = EXCLUDED.close,
            volume = EXCLUDED.volume,
            trade_count = EXCLUDED.trade_count,
            vwap = EXCLUDED.vwap,
            updated_at = EXCLUDED.updated_at;
    """
    
    try:
        with pg_conn.cursor() as cur:
            execute_values(cur, upsert_query, records)
        pg_conn.commit()
        logger.info(f"Upserted {len(records)} active 1m candles to Postgres.")
        
        for k in keys_to_delete:
            del candles_1m[k]
            
    except Exception as e:
        logger.error(f"Failed to upsert to Postgres: {e}")
        pg_conn.rollback()

def process_trade(trade):
    global raw_trades_buffer, candles_1m
    
    symbol = trade.get('s')
    if not symbol: return
    
    price = float(trade['p'])
    qty = float(trade['q'])
    ts_ms = int(trade['T'])
    
    raw_trades_buffer.append(trade)
    
    # 1-minute aggregation
    minute_ms = (ts_ms // 60000) * 60000
    key = (symbol, minute_ms)
    
    if key not in candles_1m:
        candles_1m[key] = {
            'open': price,
            'high': price,
            'low': price,
            'close': price,
            'volume': qty,
            'trade_count': 1,
            'quote_volume': price * qty
        }
    else:
        c = candles_1m[key]
        c['high'] = max(c['high'], price)
        c['low'] = min(c['low'], price)
        c['close'] = price
        c['volume'] += qty
        c['trade_count'] += 1
        c['quote_volume'] += (price * qty)

def start_consuming():
    global last_flush_time
    
    logger.info(f"Starting Kafka Consumer for topic '{KAFKA_TOPIC}'")
    
    pg_conn = None
    s3_client = None
    
    while True:
        try:
            pg_conn = get_db_connection()
            s3_client = get_s3_client()
            logger.info("Connected to Postgres and MinIO.")
            break
        except Exception as e:
            logger.error(f"Dependencies not ready, waiting 5s... {e}")
            time.sleep(5)
            
    consumer = KafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=KAFKA_BROKER,
        value_deserializer=lambda x: json.loads(x.decode('utf-8')),
        auto_offset_reset='earliest',
        enable_auto_commit=True,
        group_id='crypto-stream-consumer-group',
        api_version=(2, 8, 1)
    )
            
    logger.info("Listening for messages...")
    
    for message in consumer:
        trade = message.value
        process_trade(trade)
        
        now = time.time()
        if len(raw_trades_buffer) >= MAX_RAW_BUFFER_SIZE or (now - last_flush_time) >= FLUSH_INTERVAL_SEC:
            if raw_trades_buffer or candles_1m:
                flush_to_minio(s3_client)
                flush_to_postgres(pg_conn)
            last_flush_time = now

if __name__ == "__main__":
    start_consuming()
