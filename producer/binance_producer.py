import os
import json
import logging
import time
from dotenv import load_dotenv
import websocket
from kafka import KafkaProducer
from kafka.errors import KafkaError

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Load Environment Variables (supports running from producer/ or root/)
env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
if os.path.exists(env_path):
    load_dotenv(env_path)
    logger.info(f"Loaded environment from {env_path}")
else:
    load_dotenv() # Fallback

# For local development outside docker, swap kafka:9092 to localhost:9092
KAFKA_BROKER = os.getenv('KAFKA_BROKER', 'localhost:9092')
# Determine if running outside docker — fallback to localhost if kafka:9092 is specified but unreachable
if "kafka" in KAFKA_BROKER and not os.environ.get("RUNNING_IN_DOCKER"):
    # Simplified override for local execution testing against exposed docker ports
    KAFKA_BROKER = KAFKA_BROKER.replace("kafka", "localhost")

KAFKA_TOPIC = os.getenv('KAFKA_TOPIC_TRADES_RAW', 'crypto.trades.raw')
BINANCE_SYMBOLS = os.getenv('BINANCE_SYMBOLS', 'btcusdt,ethusdt,bnbusdt').split(',')
BINANCE_WS_BASE = os.getenv('BINANCE_WS_BASE', 'wss://stream.binance.com:9443')

# Construct the WS URL using the Combined Streams format
# Format: wss://stream.binance.com:9443/stream?streams=symbol1@trade/symbol2@trade
streams = '/'.join([f"{symbol.lower()}@trade" for symbol in BINANCE_SYMBOLS])
WS_URL = f"{BINANCE_WS_BASE}/stream?streams={streams}"

producer = None

def init_kafka_producer():
    global producer
    try:
        producer = KafkaProducer(
            bootstrap_servers=KAFKA_BROKER,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            key_serializer=lambda k: k.encode('utf-8') if k else None,
            # Add retries and reconnection settings
            retries=5,
            reconnect_backoff_ms=1000,
            api_version=(2, 8, 1) # Compatible with our cp-kafka 7.6.1 (Kafka 3.6.x API compatible)
        )
        logger.info(f"Connected to Kafka broker at {KAFKA_BROKER}")
    except Exception as e:
        logger.error(f"Failed to connect to Kafka at {KAFKA_BROKER}: {e}")
        raise

def on_message(ws, message):
    try:
        data = json.loads(message)
        # For combined streams, the payload is in data['data']
        # The stream name is in data['stream']
        if 'data' in data:
            trade_data = data['data']
            symbol = trade_data.get('s', 'UNKNOWN')
            
            # Send to Kafka using the symbol as the key for partitioning 
            # (ensures trades for the same symbol go to the same partition and maintain order)
            producer.send(KAFKA_TOPIC, key=symbol, value=trade_data)
            logger.debug(f"Pushed trade for {symbol} to Kafka")
    except Exception as e:
        logger.error(f"Error processing message: {e}")

def on_error(ws, error):
    logger.error(f"WebSocket error: {error}")

def on_close(ws, close_status_code, close_msg):
    logger.warning("WebSocket closed")

def on_open(ws):
    logger.info(f"Connected to Binance WebSocket: {WS_URL}")

def start_stream():
    logger.info(f"Starting Binance WebSocket producer for topic '{KAFKA_TOPIC}'")
    logger.info(f"Symbols monitoring: {BINANCE_SYMBOLS}")
    
    # Attempt to initialize Kafka Producer first
    while producer is None:
        try:
            init_kafka_producer()
        except Exception:
            logger.warning("Retrying Kafka connection in 5 seconds...")
            time.sleep(5)

    ws = websocket.WebSocketApp(
        WS_URL,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    
    # Run forever with automatic reconnection
    while True:
        logger.info("Starting WebSocket app loop...")
        ws.run_forever()
        logger.warning("WebSocket disconnected. Reconnecting in 5 seconds...")
        time.sleep(5)

if __name__ == "__main__":
    start_stream()
