FROM python:3.11-slim

WORKDIR /app

# Install dependencies first for better Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY binance_producer.py .

# Run the producer
CMD ["python", "-u", "binance_producer.py"]
