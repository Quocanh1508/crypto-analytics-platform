FROM python:3.11-slim

# Install libpq-dev for psycopg2 binary dependency on Debian
RUN apt-get update && apt-get install -y libpq-dev gcc && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY stream_consumer.py .

CMD ["python", "-u", "stream_consumer.py"]
