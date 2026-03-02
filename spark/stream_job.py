import os
import json
import logging
from datetime import datetime
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, from_json, window,
    first, last, max as _max, min as _min, sum as _sum, count, expr
)
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, LongType

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
if os.path.exists(env_path):
    load_dotenv(env_path)

# Environment variables
KAFKA_BROKER = os.getenv('KAFKA_BROKER', 'kafka:9092')
KAFKA_TOPIC = os.getenv('KAFKA_TOPIC_TRADES_RAW', 'crypto.trades.raw')

PG_HOST = os.getenv('POSTGRES_HOST', 'postgres')
PG_PORT = os.getenv('POSTGRES_PORT', '5432')
PG_USER = os.getenv('POSTGRES_USER', 'postgres')
PG_PASS = os.getenv('POSTGRES_PASSWORD', 'postgres')
PG_DB = os.getenv('POSTGRES_ANALYTICS_DB', 'crypto_analytics')

MINIO_HOST = os.getenv('MINIO_HOST', 'minio')
MINIO_PORT = os.getenv('MINIO_PORT', '9000')
MINIO_USER = os.getenv('MINIO_ROOT_USER', 'minioadmin')
MINIO_PASS = os.getenv('MINIO_ROOT_PASSWORD', 'minioadmin')
MINIO_BUCKET = os.getenv('MINIO_BUCKET_RAW', 'raw')

def get_db_connection():
    return psycopg2.connect(
        host=PG_HOST, port=PG_PORT, user=PG_USER, password=PG_PASS, dbname=PG_DB
    )

def upsert_to_postgres(df, epoch_id):
    """
    ForeachBatch sink function to write the aggregated 1-minute window
    into Postgres exactly as the Python consumer did.
    """
    records = df.collect()
    if not records:
        return
        
    pg_records = []
    updated_at = datetime.utcnow()
    
    for r in records:
        symbol = r.symbol
        minute_ts = r.window.start
        
        o = r.open
        h = r.high
        l = r.low
        c = r.close
        v = r.volume
        tc = r.trade_count
        quote_vol = r.quote_volume
        
        vwap = quote_vol / v if v > 0 else c
        
        pg_records.append((
            symbol, minute_ts, o, h, l, c, v, tc, vwap, updated_at
        ))
        
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
        conn = get_db_connection()
        with conn.cursor() as cur:
            execute_values(cur, upsert_query, pg_records)
        conn.commit()
        conn.close()
        logger.info(f"Batch {epoch_id}: Upserted {len(pg_records)} 1m candles to Postgres.")
    except Exception as e:
        logger.error(f"Failed to upsert Spark batch to Postgres: {e}")

def main():
    logger.info("Starting Spark Structured Streaming Job...")
    
    spark = SparkSession.builder \
        .appName("CryptoTradesAnalytics") \
        .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1,org.apache.hadoop:hadoop-aws:3.3.4,com.amazonaws:aws-java-sdk-bundle:1.12.262") \
        .config("spark.hadoop.fs.s3a.endpoint", f"http://{MINIO_HOST}:{MINIO_PORT}") \
        .config("spark.hadoop.fs.s3a.access.key", MINIO_USER) \
        .config("spark.hadoop.fs.s3a.secret.key", MINIO_PASS) \
        .config("spark.hadoop.fs.s3a.path.style.access", "true") \
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
        .config("spark.hadoop.fs.s3a.aws.credentials.provider", "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider") \
        .getOrCreate()
        
    spark.sparkContext.setLogLevel("WARN")

    # 1. Read from Kafka
    df_kafka = spark.readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", KAFKA_BROKER) \
        .option("subscribe", KAFKA_TOPIC) \
        .option("startingOffsets", "latest") \
        .load()

    # Binance trade JSON schema mapping
    # { "e": "trade", "E": 1709401736932, "s": "BTCUSDT", "t": 345678, "p": "65123.4", "q": "0.1", "T": 1709401736930 }
    schema = StructType([
        StructField("s", StringType(), True),   # Symbol
        StructField("p", StringType(), True),   # Price
        StructField("q", StringType(), True),   # Quantity
        StructField("T", LongType(), True)      # Trade timestamp (ms)
    ])

    df_parsed = df_kafka.select(from_json(col("value").cast("string"), schema).alias("data")).select("data.*")
    
    # Cast datatypes and create proper TimestampType column for Spark windowing
    df_clean = df_parsed \
        .withColumn("price", col("p").cast(DoubleType())) \
        .withColumn("quantity", col("q").cast(DoubleType())) \
        .withColumn("symbol", col("s")) \
        .withColumn("timestamp", (col("T") / 1000).cast("timestamp")) \
        .withColumn("quote_vol", col("price") * col("quantity")) \
        .drop("p", "q", "s", "T")
        
    df_clean = df_clean.filter(col("symbol").isNotNull())

    # 2. Sink A: Raw Trades to MinIO (Parquet or JSON)
    # Appending raw trades partitioned by symbol directly using Spark
    minio_query = df_clean \
        .writeStream \
        .format("json") \
        .option("path", f"s3a://{MINIO_BUCKET}/crypto_trades/") \
        .option("checkpointLocation", f"s3a://{MINIO_BUCKET}/checkpoints/raw_trades/") \
        .partitionBy("symbol") \
        .trigger(processingTime="15 seconds") \
        .start()

    # 3. Aggregation: 1-minute tumbling window
    # Mimics Python consumer OHLCV exactly.
    df_agg = df_clean \
        .withWatermark("timestamp", "1 minute") \
        .groupBy(
            window(col("timestamp"), "1 minute"),
            col("symbol")
        ) \
        .agg(
            first("price").alias("open"),
            _max("price").alias("high"),
            _min("price").alias("low"),
            last("price").alias("close"),
            _sum("quantity").alias("volume"),
            count("*").alias("trade_count"),
            _sum("quote_vol").alias("quote_volume")
        )

    # 4. Sink B: Aggregates to PostgreSQL via ForeachBatch
    pg_query = df_agg \
        .writeStream \
        .foreachBatch(upsert_to_postgres) \
        .option("checkpointLocation", f"s3a://{MINIO_BUCKET}/checkpoints/pg_agg/") \
        .trigger(processingTime="10 seconds") \
        .outputMode("update") \
        .start()

    logger.info("Streaming queries started. Awaiting termination...")
    spark.streams.awaitAnyTermination()

if __name__ == "__main__":
    main()
